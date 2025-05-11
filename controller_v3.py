
from scheduler_logger import *
from enum import Enum
import os
from threading import Thread
from time import sleep
from datetime import datetime
import docker
import urllib.parse
import psutil



LOG=SchedulerLogger()
client = docker.from_env()

benchmarks = [Job.BLACKSCHOLES, Job.CANNEAL, Job.DEDUP, Job.FERRET, Job.FREQMINE, Job.RADIX, Job.VIPS]
get_cpu_usage = lambda: psutil.cpu_percent(percpu=True, interval=None)

container_23 = None
container_1 = None


def get_image(job : Job):
    if job == Job.RADIX:
        return f"anakli/cca:splash2x_{job.value}"
    return f"anakli/cca:parsec_{job.value}"


def run_job(job : Job, cores : list[str], threads: int, quota : int =None):
    job_type = "splash2x" if job == Job.RADIX else "parsec"

    LOG.job_start(job, cores, threads)
    cpu_param = ",".join(cores)

    return client.containers.run(get_image(job), f"./run -a run -S {job_type} -p {job.value} -i native -n {threads}", detach=True, cpuset_cpus=cpu_param, name=job.value, cpu_quota=quota, remove=False)

def get_pid():
    with open("/var/run/memcached/memcached.pid", "r") as f:
        pid = f.read().strip()
        return pid


def taskset_memcached(cores: list[str]):
    os.system(f"sudo taskset -pc {",".join(cores)} {get_pid()}")
    LOG.update_cores(Job.MEMCACHED, cores)