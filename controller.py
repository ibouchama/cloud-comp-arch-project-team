import os
from time import sleep
import subprocess
import psutil
from datetime import datetime
import docker
from threading import Thread
from scheduler_logger import SchedulerLogger, Job

class SchedulerController:
    """
    Dynamic resource manager: allocates 1 or 2 cores to memcached based on CPU load
    and schedules batch jobs on dedicated cores (2,3), giving one job a 2nd core when memcached is down to 1 core.
    """
    def __init__(self,
                 benchmarks=None,
                 mem_cores=None,
                 batch_cores=None,
                 interval=0.1):
        self.client = docker.from_env()
        self.LOG = SchedulerLogger()
        
        self.benchmarks = benchmarks or [
            Job.BLACKSCHOLES, Job.DEDUP,
            Job.FERRET, Job.FREQMINE,
            Job.RADIX, Job.VIPS, Job.CANNEAL
        ]

        # reorder from longest→shortest:
        order = [Job.FREQMINE, Job.FERRET, Job.CANNEAL,
                 Job.BLACKSCHOLES, Job.VIPS, Job.RADIX, Job.DEDUP]
        self.queue = [j for j in order if j in self.benchmarks]

        # default core pools
        self.memcached_cores = mem_cores or [0,1]
        self.batch_cores = batch_cores or [2,3]
        self.interval = interval
        # pid and psutil
        self.mem_pid = self.get_memcached_pid()
        self.mem_proc = psutil.Process(self.mem_pid)
    
    def get_memcached_pid(self):
        out = subprocess.check_output(['pgrep','-x','memcached'])
        return int(out.strip())

    def adjust_mem_cores(self, cores):
        mask = ','.join(str(c) for c in cores)
        os.system(f'sudo taskset -pc {mask} {self.mem_pid}')
        self.LOG.update_cores(Job.MEMCACHED, [str(c) for c in cores])
        self.memcached_cores = cores

    def _launch_next(self):
        if not self.queue:
            return
        job = self.queue.pop(0)
        img = f"anakli/cca:{'splash2x' if job==Job.RADIX else 'parsec'}_{job.value}"
        cmd = f"./run -a run -S {('splash2x' if job==Job.RADIX else 'parsec')} \
               -p {job.value} -i native -n 2"
        c = self.client.containers.run(
            img, cmd, detach=True, name=job.value,
            cpuset_cpus="2,3", labels={"scheduler":"true"}
        )
        self.LOG.job_start(job, ["2","3"], 2)
        self.current = job

    def scheduling(self):
        for e in self.client.events(decode=True):
            if e.get("Type")=="container" and e.get("Action")=="die":
                name = self.client.containers.get(e["id"]).name
                self.LOG.job_end(Job(name))
                # as soon as one finishes we immediately start the next
                self._launch_next()
                
    def launch_all_batches(self):
        # launch every queued job on cores 2,3
        for job in self.benchmarks:
            img = f"anakli/cca:{'splash2x' if job==Job.RADIX else 'parsec'}_{job.value}"
            threads = 2
            cpus = ','.join(str(c) for c in self.batch_cores)
            self.client.containers.run(
                img, f"./run -a run -S {'splash2x' if job==Job.RADIX else 'parsec'} -p {job.value} -i native -n {threads}",
                detach=True, name=job.value, cpuset_cpus=cpus,
                labels={"scheduler":"true"}, remove=False
            )
            self.LOG.job_start(job, [str(c) for c in self.batch_cores], threads)

    def monitor_mem(self):
        # adjust memcached cores based on load
        util = self.mem_proc.cpu_percent(interval=self.interval)
        if util > 80:
            desired = [0,1]
        elif util < 60:
            desired = [0]
        else:
            desired = self.memcached_cores  # no change
        if desired != self.memcached_cores:
            self.adjust_mem_cores(desired)
            # # if mem down to 1 core, give next batch job in queue an extra core
            # if len(desired)==1 and self.queue:
            #     nextjob = self.queue.pop(0)
            #     c = self.client.containers.get(nextjob.value)
            #     newcpus = '2,3'
            #     c.update(cpuset_cpus=newcpus)
            #     self.LOG.update_cores(nextjob, ['2','3'])
            # if mem down to 1 core, give the *currently running* batch job a second core
            if len(desired)==1 and hasattr(self, 'current'):
                c = self.client.containers.get(self.current.value)
                c.update(cpuset_cpus="2,3")
                self.LOG.update_cores(self.current, ['2','3'])

    def run(self):
        # clean up
        for c in self.client.containers.list(all=True, filters={"label":["scheduler=true"]}):
            try: c.kill()
            except: pass
            finally: c.remove(force=True)
        # log start
        self.LOG._log("start", Job.SCHEDULER)
        self.LOG.job_start(Job.MEMCACHED, [str(c) for c in self.memcached_cores], len(self.memcached_cores))
        self.adjust_mem_cores(self.memcached_cores)
        # start mem monitor thread
        t = Thread(target=lambda: [self.monitor_mem() or sleep(self.interval) for _ in iter(int,1)], daemon=True)
        t.start()

        # 4) Start the Docker-event watcher that will re-launch jobs
        watcher = Thread(target=self.scheduling, daemon=True)
        watcher.start()

        # 5) Kick off exactly one batch job (the longest one, per your pre-sorted queue)
        self._launch_next()

        # wait for all to finish
        while self.client.containers.list(filters={"label":["scheduler=true"],"status":"running"}):
            sleep(self.interval)
        # done
        self.LOG.job_end(Job.MEMCACHED)
        self.LOG._log("end", Job.SCHEDULER)

if __name__=='__main__':
    SchedulerController().run()
