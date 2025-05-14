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
    def __init__(self, benchmarks=None, mem_cores=None, batch_cores=None, interval=0.1):
        # Docker client and logger
        self.client = docker.from_env()
        self.LOG = SchedulerLogger()
        # Job list and scheduling parameters
        self.benchmarks = benchmarks or [
            Job.BLACKSCHOLES, Job.CANNEAL, Job.DEDUP,
            Job.FERRET, Job.FREQMINE, Job.RADIX, Job.VIPS
        ]
        self.main_container = None
        self.shared_container = None
        self.queue = self.benchmarks.copy()
        # Memcached / batch core pools
        self.memcached_cores = mem_cores or [0,1]
        self.batch_cores = batch_cores or [2, 3]
        # Runtime state
        self.interval = interval
        # Discover memcached PID
        self.memcached_pid = self._get_memcached_pid()
        self.process = psutil.Process(int(self.memcached_pid))
        self.cpu_percent = lambda: psutil.cpu_percent(percpu=True, interval=None)
        self.cpu_mem_percent = lambda : psutil.virtual_memory().percent
        # self.quota
        # self.prev_quota = 100000
        # start off assuming full quota
        self.prev_quota = 100000
        self.quota = self.prev_quota

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
        mode = 'splash2x' if job == Job.RADIX else 'parsec'
        img = f"anakli/cca:{mode}_{job.value}"
        cmd = f"./run -a run -S {mode} -p {job.value} -i native -n 2"
        cpus = ','.join(str(c) for c in self.batch_cores)
        self.main_container = self.client.containers.run(
            img, cmd, detach=True, name=job.value, cpuset_cpus=cpus, labels={"scheduler" : "true"}
        )
        self.LOG.job_start(job, [str(c) for c in self.batch_cores], 2)

    def _launch_canneal(self):
        job = Job.CANNEAL
        img = f"anakli/cca:parsec_{job.value}"
        cmd = f"./run -a run -S parsec -p {job.value} -i native -n 1"
        cpus = '1'
        self.shared_container = self.client.containers.run(
            img, cmd, detach=True, name=job.value, cpuset_cpus=cpus, labels={"scheduler" : "true"}
        )
        self.LOG.job_start(job, ["1"], 1)


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
            if event.get('Type') == 'container' and event.get('Action') in ['die', 'stop']:
                time = datetime.now().timestamp()
                container_id = event.get('id')
                container = self.client.containers.get(container_id)
                job = Job(container.name)
                self.LOG.job_end(job)
                time = datetime.now().timestamp() - time
                print(f"Event handling for {job} took {time} seconds")
                self._launch_next()
        
    
    def remove_containers(self):
        to_remove = self.client.containers.list(
            all=True,
            filters={"label" : ["scheduler=true"]}
        )

        for container in to_remove:
            try:
                container.stop(timeout=5)
            except docker.errors.APIError:
                container.kill()
            finally:
                container.remove(force=True)


    def run(self):
        # self.remove_containers()
        # self.LOG.__init__()
        # start = datetime.now()
        # self.LOG.job_start(Job.MEMCACHED, ["0", "1"], 2)
        # self._adjust_mem_cores(self.memcached_cores)
        # self._launch_canneal()
        # self._launch_next()
        # t=Thread(target=self.scheduling, daemon=True)
        # t.start()
        self.remove_containers()
        self.LOG.__init__()
        start = datetime.now()
        self.LOG.job_start(Job.MEMCACHED, ["0", "1"], 2)
        # start listening *before* we fire off any containers
        t = Thread(target=self.scheduling, daemon=True)
        t.start()

        self._adjust_mem_cores(self.memcached_cores)
        self._launch_canneal()
        self._launch_next()
        
        while self.client.containers.list(filters={"label" : ["scheduler=true"], "status" : "running"}) or self.queue:
            time = datetime.now().timestamp()
            self.memcached_quotas()
            time = datetime.now().timestamp() - time
            print(f"handling the memcached job quotas took {time} seconds") 
        
        end = datetime.now()
        print(f"Execution finished in {start - end}. Running for 60 more seconds")
        sleep(60)
        self.LOG.job_end(Job.MEMCACHED)
        self.LOG.end()



# Example usage
if __name__ == '__main__':
    controller = SchedulerController()
    controller.run()
