import subprocess
import time
import psutil
import docker
from scheduler_logger import SchedulerLogger

# === Config ===
MEMCACHED_PID = int(subprocess.getoutput("pidof memcached").strip())
BATCH_JOBS = [
    ("blackscholes", "anakli/cca:parsec_blackscholes"),
    ("canneal", "anakli/cca:parsec_canneal"),
    ("dedup", "anakli/cca:parsec_dedup"),
    ("ferret", "anakli/cca:parsec_ferret"),
    ("freqmine", "anakli/cca:parsec_freqmine"),
    ("radix", "anakli/cca:splash2x_radix"),
    ("vips", "anakli/cca:parsec_vips"),
]
CORES = [0, 1, 2, 3]
MEMCACHED_MIN_CORES = 1
MEMCACHED_MAX_CORES = 2
SLO_LATENCY = 0.8  # milliseconds

# === Init ===
client = docker.from_env()
logger = SchedulerLogger("jobs_1.txt")  # Change per run
logger.start("scheduler")

def set_memcached_cores(cores):
    cmd = f"taskset -cp {','.join(map(str, cores))} {MEMCACHED_PID}"
    subprocess.run(cmd, shell=True, check=True)
    logger.update_cores("memcached", cores)

def run_job(name, image, cores, threads):
    container = client.containers.run(
        image,
        f"./run -a run -S parsec -p {name} -i native -n {threads}",
        cpuset_cpus=",".join(map(str, cores)),
        detach=True,
        name=name,
        remove=True,
    )
    logger.start(name, cores, threads)
    return container

def monitor_mcperf_latency(mcperf_file="mcperf_1.txt"):
    # Replace this with actual tail latency reading logic
    try:
        with open(mcperf_file, "r") as f:
            lines = f.readlines()
            latencies = [float(line.split()[-1]) for line in lines if "percentile" in line]
            return latencies[-1] if latencies else 0.5
    except:
        return 0.5

# === Main Control Loop ===
def main():
    set_memcached_cores([0])
    batch_containers = []
    available_cores = [1, 2, 3]

    for job_name, job_image in BATCH_JOBS:
        # Basic resource allocation strategy
        if len(available_cores) < 1:
            print(f"Waiting for cores to be available for {job_name}")
            time.sleep(5)
            continue

        job_cores = [available_cores.pop(0)]
        container = run_job(job_name, job_image, job_cores, threads=1)
        batch_containers.append((job_name, container, job_cores))

        # Adjust memcached cores if needed
        latency = monitor_mcperf_latency()
        if latency > SLO_LATENCY:
            print(f"High latency: {latency:.2f}ms → increasing memcached cores")
            if len(available_cores) > 0:
                memcached_cores = [0, available_cores.pop(0)]
                set_memcached_cores(memcached_cores)

        time.sleep(10)  # Allow system to stabilize

    # Monitor for job completions
    while batch_containers:
        for i, (name, container, cores) in enumerate(batch_containers):
            container.reload()
            if container.status == "exited":
                logger.end(name)
                available_cores.extend(cores)
                batch_containers.pop(i)
        time.sleep(5)

    logger.end("scheduler")

if __name__ == "__main__":
    main()
