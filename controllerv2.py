#!/usr/bin/env python3

import subprocess
import time
import re
import os
import signal
import shlex
from datetime import datetime, timezone

# --- Configuration ---
LOG_FILE_PATH = "controller_execution_log.txt" # This will be one of jobs_N.txt
MCPERF_OUTPUT_FILE = "mcperf_controller_run.txt" # This will be one of mcperf_N.txt

MEMCACHED_SERVER_IP = "10.138.0.31" # Internal IP of the memcache-server-qmql VM
MEMCACHED_PORT = 11211
MEMCACHED_SLO_MS = 0.8
MEMCACHED_INITIAL_CORES = [0] # Start with 1 core
MEMCACHED_SCALED_CORES = [0, 1] # Scale up to 2 cores
MEMCACHED_PID = None # To be fetched

MCPERF_AGENT_IP = "10.138.0.33" # Internal IP of client-agent-bf7q VM
MCPERF_CLIENT_MEASURE_VM_USER = "ubuntu" # Assuming ubuntu user on mcperf VMs

# mcperf dynamic load parameters
MCPERF_DURATION_SECONDS = 300 # Example: run for 5 minutes. Adjust as needed.
MCPERF_QPS_INTERVAL = 2
MCPERF_QPS_MIN = 5000
MCPERF_QPS_MAX = 180000
MCPERF_THREADS = 8 # As per Part 4 example

VM_TOTAL_CORES = 4
CONTROLLER_LOOP_INTERVAL = 2 # Seconds

# Batch Job Definitions (using native dataset as per Part 4)
# Threads: Rule of thumb: num_cores_assigned. Max 4 for these 4-core VMs.
BATCH_JOBS_SPECS = {
    "blackscholes": {"image": "anakli/cca:parsec_blackscholes", "cmd_template": "./run -a run -S parsec -p blackscholes -i native -n {threads}"},
    "canneal":      {"image": "anakli/cca:parsec_canneal",      "cmd_template": "./run -a run -S parsec -p canneal -i native -n {threads}"},
    "dedup":        {"image": "anakli/cca:parsec_dedup",        "cmd_template": "./run -a run -S parsec -p dedup -i native -n {threads}"},
    "ferret":       {"image": "anakli/cca:parsec_ferret",       "cmd_template": "./run -a run -S parsec -p ferret -i native -n {threads}"},
    "freqmine":     {"image": "anakli/cca:parsec_freqmine",     "cmd_template": "./run -a run -S parsec -p freqmine -i native -n {threads}"},
    "radix":        {"image": "anakli/cca:splash2x_radix",      "cmd_template": "./run -a run -S splash2x -p radix -i native -n {threads}"},
    "vips":         {"image": "anakli/cca:parsec_vips",         "cmd_template": "./run -a run -S parsec -p vips -i native -n {threads}"},
}
# Based on sensitivity table and general knowledge:
# radix is least sensitive. ferret/freqmine are very sensitive.
BATCH_JOB_ORDER = ["radix", "blackscholes", "canneal", "vips", "dedup", "freqmine", "ferret"]

# --- Utility Functions ---
def run_command(command, shell=False, check=True, capture_output=False, text=True):
    print(f"EXEC: {command}")
    try:
        if capture_output:
            result = subprocess.run(command, shell=shell, check=check, capture_output=True, text=text)
            return result.stdout.strip(), result.stderr.strip()
        else:
            subprocess.run(command, shell=shell, check=check)
            return None, None
    except subprocess.CalledProcessError as e:
        print(f"Command '{command}' failed with error: {e}")
        if capture_output:
            return e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else ""
        raise
    except Exception as e:
        print(f"An unexpected error occurred with command '{command}': {e}")
        if capture_output:
            return "", str(e)
        raise

def get_memcached_pid():
    try:
        stdout, _ = run_command("pgrep memcached", shell=True, capture_output=True)
        return int(stdout)
    except Exception as e:
        print(f"Error getting memcached PID: {e}")
        return None

def set_memcached_affinity(pid, cores):
    core_str = ",".join(map(str, cores))
    run_command(f"sudo taskset -pc {core_str} {pid}")
    logger.update_cores("memcached", cores)
    return cores

# --- Job Logger ---
class JobLogger:
    def __init__(self, filepath):
        self.filepath = filepath
        # Clear file or create if not exists
        with open(self.filepath, 'w') as f:
            pass 

    def _log(self, event_name, job_name, params=None):
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        log_line = f"{timestamp} {event_name} {job_name}"
        if params:
            log_line += " " + " ".join(map(str, params))
        
        print(f"LOG: {log_line}") # Also print to console for live feedback
        with open(self.filepath, 'a') as f:
            f.write(log_line + "\n")

    def start_scheduler(self):
        self._log("start", "scheduler")

    def end_scheduler(self):
        self._log("end", "scheduler")

    def start_job(self, job_name, cores_assigned, threads):
        # Format cores_assigned as a list string for logging, e.g., "[0,1,2]"
        cores_str = f"[{','.join(map(str, sorted(list(cores_assigned))))}]"
        self._log("start", job_name, [cores_str, threads])

    def end_job(self, job_name):
        self._log("end", job_name)

    def update_cores(self, job_name, new_cores):
        cores_str = f"[{','.join(map(str, sorted(list(new_cores))))}]"
        self._log("update_cores", job_name, [cores_str])
    
    def custom_event(self, job_name, message):
        import urllib.parse
        self._log("custom", job_name, [urllib.parse.quote_plus(message)])

logger = JobLogger(LOG_FILE_PATH)

# --- CPU Utilization ---
class CPUUtil:
    def __init__(self):
        self.prev_idle = 0
        self.prev_total = 0
        self._get_cpu_times() # Initialize prev values

    def _get_cpu_times(self):
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        parts = line.split()
        # user nice system idle iowait irq softirq steal guest guest_nice
        # We need the first CPU line 'cpu' (aggregate)
        idle = int(parts[4]) + int(parts[5]) # idle + iowait
        total = sum(map(int, parts[1:8])) # Sum of user, nice, system, idle, iowait, irq, softirq
        return idle, total

    def get_utilization(self):
        current_idle, current_total = self._get_cpu_times()
        delta_idle = current_idle - self.prev_idle
        delta_total = current_total - self.prev_total
        self.prev_idle, self.prev_total = current_idle, current_total

        if delta_total == 0: # Avoid division by zero if no time has passed or no activity
            return 0.0
        
        utilization = (1.0 - (delta_idle / delta_total)) * 100
        return utilization

cpu_monitor = CPUUtil()

# --- Main Controller Logic ---
mcperf_process = None
current_batch_job_process = None
current_batch_job_name = None
current_memcached_cores = []

def cleanup():
    global mcperf_process, current_batch_job_process
    print("Cleaning up...")
    if mcperf_process:
        print("Terminating mcperf...")
        mcperf_process.terminate()
        try:
            mcperf_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mcperf_process.kill()
        mcperf_process = None
    
    if current_batch_job_process:
        print(f"Terminating current batch job: {current_batch_job_name}...")
        try:
            # Try to stop Docker container gracefully first
            run_command(f"sudo docker stop {current_batch_job_name}", check=False)
            time.sleep(2) # Give it a moment
            run_command(f"sudo docker rm {current_batch_job_name}", check=False) 
        except Exception as e:
            print(f"Error stopping/removing docker container {current_batch_job_name}: {e}")
        
        # If process was started with subprocess.Popen directly (not docker)
        if hasattr(current_batch_job_process, 'terminate'):
             current_batch_job_process.terminate()
             try:
                current_batch_job_process.wait(timeout=5)
             except subprocess.TimeoutExpired:
                current_batch_job_process.kill()
        current_batch_job_process = None

    # Ensure memcached is running (it should be managed by systemd, but for safety)
    # If it was started by this script (not the case here as per instructions), stop it.
    logger.end_scheduler()
    print("Cleanup complete.")

def parse_mcperf_latency(line):
    # Example line from augmented mcperf:
    # [  1] Sending 2s (2000000us) |  25000.0  25000.0 |   603us   112us |   50%:   598us |   90%:   698us |   95%:   742us |   99%:   830us |   Ops: 50000 (0) | Start: 1678886400 End: 1678886402
    match = re.search(r"95%:\s*(\d+)us", line)
    if match:
        return int(match.group(1)) / 1000.0  # Convert to ms
    return None

def start_memcached_service():
    global MEMCACHED_PID, current_memcached_cores
    print("Ensuring memcached service is running and configured...")
    # Assuming memcached is already installed and configured to listen on MEMCACHED_SERVER_IP:MEMCACHED_PORT
    # and with 1024MB memory as per Part 4 setup.
    # We just need to restart it to apply systemd config, then get PID and set affinity.
    try:
        run_command("sudo systemctl restart memcached")
        time.sleep(2) # Give it a moment to restart
        MEMCACHED_PID = get_memcached_pid()
        if not MEMCACHED_PID:
            raise Exception("Failed to get memcached PID after restart.")
        
        current_memcached_cores = set_memcached_affinity(MEMCACHED_PID, MEMCACHED_INITIAL_CORES)
        logger.start_job("memcached", current_memcached_cores, 1) # Assuming 1 main memcached software thread
        print(f"Memcached started (PID: {MEMCACHED_PID}) on cores {current_memcached_cores}")
    except Exception as e:
        print(f"FATAL: Could not start or configure memcached: {e}")
        raise

def start_mcperf():
    global mcperf_process
    # mcperf commands for Part 4 dynamic load
    # 1. Load data (on client-measure VM) - this should be done once MANUALLY or via SSH
    # For controller, we assume it's loaded. We start the dynamic query.
    # The controller runs on memcached-server, mcperf client runs on client-measure.
    # So we need to SSH to client-measure to run mcperf.
    # Simpler: For this script, assume mcperf runs LOCALLY for testing, or adapt to use SSH.
    # For now, let's write the command as if running on the client-measure VM,
    # then we'll wrap it in SSH or assume user runs it separately and pipes output.
    
    # The prompt implies the augmented mcperf is on client-agent and client-measure.
    # The dynamic load generation happens on client-measure.
    # We need to get output from client-measure. Simplest: run mcperf on client-measure,
    # redirect its output to a file on a shared volume, or SSH and capture.
    # For this exercise, let's assume we SSH and run it.
    
    # *** This part is tricky. For a self-contained controller, it would need SSH keys set up. ***
    # *** A simpler approach for the project might be to run mcperf manually on client-measure ***
    # *** and have it write its output to a file that the controller can read (e.g., via NFS or scp periodically). ***
    # *** For now, I'll simulate mcperf by creating a Popen object that would represent the SSH command. ***
    
    # The mcperf command as per instructions page 20:
    mcperf_cmd_on_client = (
        f"./mcperf -s {MEMCACHED_SERVER_IP} -a {MCPERF_AGENT_IP} "
        f"--noload -T {MCPERF_THREADS} -C 8 -D 4 -Q 1000 -c 8 -t {MCPERF_DURATION_SECONDS} "
        f"--qps_interval {MCPERF_QPS_INTERVAL} --qps_min {MCPERF_QPS_MIN} --qps_max {MCPERF_QPS_MAX}"
    )
    
    # Simplified: For the purpose of this script, we'll run a dummy mcperf if SSH is too complex.
    # Let's assume the user will run mcperf on the client-measure VM and pipe its output to MCPERF_OUTPUT_FILE
    # on the memcached server where this controller runs.
    # This controller will then tail this file.
    
    # So, this function will just open the file for reading.
    print(f"Controller expects mcperf output in: {MCPERF_OUTPUT_FILE}")
    print("Please ensure mcperf is running on the client-measure VM and its output is redirected to this file.")
    print(f"Example mcperf command to run on client-measure VM:")
    print(f"  cd memcache-perf-dynamic && {mcperf_cmd_on_client} > /path/to/shared/{MCPERF_OUTPUT_FILE}")
    print("Alternatively, for testing, create a dummy mcperf_output.txt with sample lines.")

    # Create the file if it doesn't exist, so `tail` doesn't fail immediately
    if not os.path.exists(MCPERF_OUTPUT_FILE):
        with open(MCPERF_OUTPUT_FILE, 'w') as f:
            f.write("# mcperf output will appear here\n")

    # We will use subprocess to tail the file
    # This allows non-blocking reads of new lines.
    cmd = shlex.split(f"tail -F -n 0 {MCPERF_OUTPUT_FILE}")
    mcperf_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("Tailing mcperf output file...")


def main():
    global mcperf_process, current_batch_job_process, current_batch_job_name, current_memcached_cores
    
    # Trap SIGINT and SIGTERM to cleanup
    signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), exit(0)))
    signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup(), exit(0)))

    logger.start_scheduler()

    try:
        start_memcached_service()
        start_mcperf() # This now sets up tailing the output file

        pending_batch_jobs = list(BATCH_JOB_ORDER)
        completed_batch_jobs = set()
        
        last_latency_check_time = time.time()
        latest_95th_latency = None

        while len(completed_batch_jobs) < len(BATCH_JOB_ORDER):
            current_time = time.time()
            
            # 1. Check mcperf output for new latency
            # Non-blocking read from mcperf_process (tail -F)
            if mcperf_process.stdout:
                line = mcperf_process.stdout.readline() # This will block if no new line
                                                        # Consider select or fcntl for true non-blocking.
                                                        # For simplicity, a short timeout or rely on tail's behavior.
                                                        # A simple readline() will work if mcperf output is frequent enough.
                while line: # Read all available lines
                    print(f"MCPERF_RAW: {line.strip()}")
                    parsed_lat = parse_mcperf_latency(line.strip())
                    if parsed_lat is not None:
                        latest_95th_latency = parsed_lat
                        logger.custom_event("mcperf", f"New latency: {latest_95th_latency:.3f} ms")
                    if not mcperf_process.stdout: break # stdout might be closed
                    # Check if more lines are immediately available (very basic non-blocking check)
                    mcperf_process.stdout.peek(1) 
                    line = mcperf_process.stdout.readline()


            # 2. Adjust memcached cores based on SLO
            if latest_95th_latency is not None:
                if latest_95th_latency > MEMCACHED_SLO_MS and len(current_memcached_cores) < len(MEMCACHED_SCALED_CORES):
                    print(f"Latency ({latest_95th_latency:.3f}ms) > SLO ({MEMCACHED_SLO_MS}ms). Scaling up memcached.")
                    current_memcached_cores = set_memcached_affinity(MEMCACHED_PID, MEMCACHED_SCALED_CORES)
                    logger.custom_event("memcached", f"Scaled up to {len(current_memcached_cores)} cores due to SLO miss.")
                elif latest_95th_latency < (MEMCACHED_SLO_MS * 0.7) and len(current_memcached_cores) > len(MEMCACHED_INITIAL_CORES): # Hysteresis
                    # Only scale down if we have cores to give back OR if no batch job is running/waiting
                    # For now, simpler: scale down if latency is good.
                    print(f"Latency ({latest_95th_latency:.3f}ms) well within SLO. Scaling down memcached.")
                    current_memcached_cores = set_memcached_affinity(MEMCACHED_PID, MEMCACHED_INITIAL_CORES)
                    logger.custom_event("memcached", f"Scaled down to {len(current_memcached_cores)} cores, SLO met.")
                latest_95th_latency = None # Consume the reading

            # 3. Manage batch jobs
            available_cores_for_batch = [c for c in range(VM_TOTAL_CORES) if c not in current_memcached_cores]
            
            if current_batch_job_process: # A job is running
                ret_code = current_batch_job_process.poll()
                if ret_code is not None: # Job finished
                    print(f"Batch job {current_batch_job_name} finished with code {ret_code}.")
                    logger.end_job(current_batch_job_name)
                    if ret_code == 0:
                        completed_batch_jobs.add(current_batch_job_name)
                    else:
                        # Optionally retry or mark as failed and move on
                        logger.custom_event(current_batch_job_name, f"Failed with exit code {ret_code}")
                        completed_batch_jobs.add(current_batch_job_name) # Mark as 'handled'
                    current_batch_job_process = None
                    current_batch_job_name = None
            
            if not current_batch_job_process and pending_batch_jobs: # No job running, and jobs are pending
                if available_cores_for_batch:
                    job_name_to_run = pending_batch_jobs.pop(0)
                    current_batch_job_name = job_name_to_run
                    spec = BATCH_JOBS_SPECS[job_name_to_run]
                    
                    num_threads_for_job = min(len(available_cores_for_batch), 4) # Max 4 threads, or num available cores
                    
                    # Docker command
                    # Using --rm to auto-remove container on exit
                    # Naming the container allows easier management if needed (e.g. docker stop job_name_to_run)
                    docker_cpuset = ",".join(map(str, available_cores_for_batch))
                    docker_cmd_str = spec['cmd_template'].format(threads=num_threads_for_job)
                    
                    full_docker_cmd = (
                        f"sudo docker run --rm --name {job_name_to_run} "
                        f"--cpuset-cpus='{docker_cpuset}' {spec['image']} {docker_cmd_str}"
                    )
                    
                    print(f"Starting batch job: {job_name_to_run} on cores {available_cores_for_batch} with {num_threads_for_job} threads.")
                    # Run Docker command in background
                    current_batch_job_process = subprocess.Popen(shlex.split(full_docker_cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    logger.start_job(job_name_to_run, available_cores_for_batch, num_threads_for_job)
                else:
                    print("No cores available for batch jobs right now.")

            # 4. Get CPU utilization (optional, for logging or more advanced decisions)
            # util = cpu_monitor.get_utilization()
            # print(f"Current CPU Utilization: {util:.2f}%")
            # logger.custom_event("system", f"CPU_util: {util:.2f}%")


            time.sleep(CONTROLLER_LOOP_INTERVAL)

        print("All batch jobs completed.")

    except Exception as e:
        print(f"An error occurred in the main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()

if __name__ == "__main__":
    # Ensure script is run with sudo for taskset and docker, or user is in docker group
    if os.geteuid() != 0:
        print("Warning: This script may need root privileges for 'taskset' and 'docker'.")
        print("Ensure your user is in the 'docker' group for passwordless docker access.")
        # For taskset, you might need to run `sudo python3 controller.py`
        # Or configure sudoers for passwordless taskset for this user.
    main()