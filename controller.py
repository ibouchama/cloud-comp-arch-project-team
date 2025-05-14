import os
from time import sleep
import subprocess
import docker.errors
import psutil
from datetime import datetime
import docker
from threading import Thread
from scheduler_logger import SchedulerLogger, Job, LOG_STRING

class SchedulerController:
    """
    Encapsulates memcached core management and PARSEC batch job scheduling.
    """
    def __init__(self, benchmarks=None,
                 mem_cores=None, batch_cores=None,
                 colocated_jobs=None,
                 interval=0.1):
        # Docker client and logger
        self.client = docker.from_env()
        self.LOG = SchedulerLogger()

        # Job list
        self.benchmarks = benchmarks or [
            Job.BLACKSCHOLES, Job.DEDUP,
            Job.FERRET, Job.FREQMINE, Job.RADIX, Job.VIPS
        ]
        self.queue = self.benchmarks.copy()

        # Which jobs should share the memcached cores
        self.colocated_jobs = colocated_jobs or [Job.CANNEAL]

        # Core pools
        self.memcached_cores = mem_cores or [0, 1]
        self.batch_cores = batch_cores or [2, 3]

        # Runtime state
        self.interval = interval
        # For quota‐based throttling:
        self.cpu_percent = lambda: psutil.cpu_percent(percpu=False, interval=None)
        self.prev_quota = 100_000       # μs of CPU per 100 ms period → 100% of one core
        self.quota      = self.prev_quota

        self.cpu_mem_percent = lambda : psutil.virtual_memory().percent

        # Discover memcached PID
        self.memcached_pid = self._get_memcached_pid()
        self.process = psutil.Process(int(self.memcached_pid))

    def _get_memcached_pid(self):
        try:
            out = subprocess.check_output(['pgrep', '-x', '-n', 'memcached'])
            return int(out.strip())
        except subprocess.CalledProcessError:
            raise RuntimeError('memcached not running')

    def _adjust_mem_cores(self, cores):
        cores_str = ','.join(str(c) for c in cores)
        os.system(f'sudo taskset -pc {cores_str} {self.memcached_pid}')
        self.LOG.update_cores(Job.MEMCACHED, [str(c) for c in cores])
        self.memcached_cores = cores

    def _launch_next(self):
        if not self.queue:
            return
        job = self.queue.pop(0)
        # decide which cores to use
        if job in self.colocated_jobs:
            cpus = ','.join(str(c) for c in self.memcached_cores)
            cores_logged = [str(c) for c in self.memcached_cores]
        else:
            cpus = ','.join(str(c) for c in self.batch_cores)
            cores_logged = [str(c) for c in self.batch_cores]

        mode = 'splash2x' if job == Job.RADIX else 'parsec'
        img = f"anakli/cca:{mode}_{job.value}"
        cmd = f"./run -a run -S {mode} -p {job.value} -i native -n 2"
        self.main_container = self.client.containers.run(
            img, cmd, detach=True, name=job.value,
            cpuset_cpus=cpus, labels={"scheduler": "true"}
        )
        self.LOG.job_start(job, cores_logged, 2)

    def _launch_canneal(self):
        # always colocated on memcached cores
        job = Job.CANNEAL
        cpus = ','.join(str(c) for c in self.memcached_cores)
        img = f"anakli/cca:parsec_{job.value}"
        cmd = f"./run -a run -S parsec -p {job.value} -i native -n 1"
        self.shared_container = self.client.containers.run(
            img, cmd, detach=True, name=job.value,
            cpuset_cpus=cpus, labels={"scheduler": "true"}
        )
        self.LOG.job_start(job, [str(c) for c in self.memcached_cores], 1)

    def memcached_quotas(self):
        memcached_cpu = self.process.cpu_percent(interval=self.interval)

        if memcached_cpu > 95:
            self.quota = 0
        elif memcached_cpu > 80:
            self.quota = 10000
        elif memcached_cpu > 75:
            self.quota = 20000
        elif memcached_cpu > 65:
            self.quota = 30000
        elif memcached_cpu > 60:
            self.quota = 35000
        elif memcached_cpu > 50:
            self.quota = 40000
        elif memcached_cpu > 45:
            self.quota = 50000
        elif memcached_cpu > 35:
            self.quota = 60000
        elif memcached_cpu > 20:
            self.quota = 20000
        else:
            self.quota = 100000
        
        mem_usage = self.cpu_mem_percent()

        if self.quota != self.prev_quota:
            try:
                if self.prev_quota == 0:
                    self.shared_container.unpause()
                    self.LOG.job_unpause(Job(self.shared_container.name))
                elif self.quota == 0:
                    self.shared_container.pause()
                    self.LOG.job_pause(Job(self.shared_container.name))
            except Exception as e:
                print(f"Error pausing/unpausing {Job(self.shared_container.name)} : {e}")

            if self.quota == 100000:
                self._adjust_mem_cores([0])
            elif self.prev_quota == 100000:
                self._adjust_mem_cores([0,1])

            try:
                self.shared_container.update(cpu_quota=self.quota)
            except Exception as e:
                print(f"Error updating quotas in shared container for core 1: {e} ")
        

        self.prev_quota = self.quota
        #TODO: Log data

    def scheduling(self):
        for event in self.client.events(decode=True):
            if event.get('Type') == 'container' and event.get('Action') == 'die':
                container_id = event.get('id')
                container = self.client.containers.get(container_id)
                job = Job(container.name)
                self.LOG.job_end(job)
                self._launch_next()

    def remove_containers(self):
        to_remove = self.client.containers.list(
            all=True,
            filters={"label": ["scheduler=true"]}
        )
        for c in to_remove:
            try:
                c.stop(timeout=5)
            except docker.errors.APIError:
                c.kill()
            finally:
                c.remove(force=True)

    def run(self):
        # teardown any leftovers
        self.remove_containers()
        # reinitialize log
        self.LOG.__init__()
        start = datetime.now()

        # pin memcached to its cores
        self.LOG.job_start(Job.MEMCACHED,
                           [str(c) for c in self.memcached_cores],
                           len(self.memcached_cores))
        self._adjust_mem_cores(self.memcached_cores)

        # start listening for exit events
        t = Thread(target=self.scheduling, daemon=True)
        t.start()

        # launch canneal (shared) and first batch job
        self._launch_canneal()
        self._launch_next()

        # busy‐wait until no more jobs
        while (self.client.containers.list(
                   filters={"label": ["scheduler=true"], "status": "running"}
               ) or self.queue):
            # measure memcached CPU usage and update cpu_quota / pause‐unpause
            self.memcached_quotas()
            # sleep a bit before re‐sampling
            sleep(self.interval)
        
        # all done: leave memcached alone for 60s
        elapsed = datetime.now() - start
        print(f"Finished batch in {elapsed}, idling 60s…")
        sleep(60)
        self.LOG.job_end(Job.MEMCACHED)
        self.LOG.end()

if __name__ == '__main__':
    # Example: run canneal and blackscholes on memcores, others on 2-3
    controller = SchedulerController(
        colocated_jobs=[Job.CANNEAL, Job.BLACKSCHOLES]
    )
    controller.run()
