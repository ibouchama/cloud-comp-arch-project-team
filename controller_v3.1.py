import os
import time
import subprocess
import psutil
from datetime import datetime
import docker
from scheduler_logger import SchedulerLogger, Job

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
        cont = self.client.containers.run( #run with Docker
            img, cmd, detach=True, name=job.value, cpuset_cpus=cpus
        )
        self.LOG.job_start(job, [str(c) for c in self.batch_cores], 2)


    def memcached_quotas(self, prev_quota=100000):
        memcached_cpu = self.process.cpu_percent(interval=self.interval)

        quota = max(0, (95 - memcached_cpu)*1000)

    def run(self):
        start = datetime.now()
        self._adjust_mem_cores([0,1])
        self.LOG.job_start(Job.MEMCACHED, ["0", "1"], 2)

# Example usage
if __name__ == '__main__':
    controller = SchedulerController()
    controller.run()
