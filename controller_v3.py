
from scheduler_logger import *
from enum import Enum
import os
from threading import Thread
from time import sleep
from datetime import datetime
import docker
import urllib.parse
import psutil
import subprocess



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
    try:
        output = subprocess.check_output(['pgrep', '-x', '-n', "memcached"])
        pid = int(output.strip())
        return pid
    except subprocess.CalledProcessError as e:
        print(f"Can't find the pid : {e}")
        return None


def taskset_memcached(cores: list[str]):
    os.system(f"sudo taskset -pc {",".join(cores)} {get_pid()}")
    LOG.update_cores(Job.MEMCACHED, cores)

def update_docker(container, quota: int =None, cores: list[str]=["0"]):
    try:
        container.update(cpuset_cpus=",".join(cores), cpu_quota=quota)
    except Exception as e:
        print(f"error updating container {container} : {e}")


def next_benchmark(previous_job : Job):

    match previous_job:
        case Job.BLACKSCHOLES:
            container_23 = run_job(Job.DEDUP, ["2", "3"], 2)
        case Job.DEDUP:
            container_23 = run_job(Job.FERRET, ["2", "3"], 2)
        case Job.FERRET:
            container_23 = run_job(Job.FREQMINE, ["2", "3"], 2)
        case Job.FREQMINE:
            container_23 = run_job(Job.RADIX, ["2", "3"], 2)
        case Job.RADIX:
            container_23 = run_job(Job.VIPS, ["2", "3"], 2)
        case Job.VIPS:
            update_docker(container_1, quota=100000, cores=["2", "3"])

