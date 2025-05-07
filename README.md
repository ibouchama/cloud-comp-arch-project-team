To set-up the environment, create a new bucket and a new cluster within, run the following instructions:

- source env_setup.sh
- bash create_bucket.sh
- bash create_cluster.sh
  If you encounter an error when running the above, try the following set of commands:
- - gcloud auth login
- - gcloud auth application-default login
- - source env_setup.sh
- - export PROJECT=$(gcloud config get-value project)
- - export KOPS_STATE_STORE=gs://cca-eth-2025-group-94-ibouchama/

Your cluster should now be created. Verify with the following command and get the names of the vms:

- kubectl get nodes -o wide
  You should see 4 nodes: 1 master and 3 nodes

To launch memcached, run this:

- bash launch_memcached.sh

Now ssh into the VM and build mcperf:

Replace the NODE_NAME (names of the vms) with the name of the node you would like to ssh into.
Should have the following form:

- NODE_NAME1 = client-agent-XXXXand (Run mcperf -T 8 -A (the agent))
- NODE_NAME2 = client-measure-XXXX (Run mcperf load generation and measurement)

Copy the mcperf build file into the VMS

- gcloud compute scp install_mcperf.sh ubuntu@NODE_NAME1:~ --zone europe-west1-b
- gcloud compute scp install_mcperf.sh ubuntu@NODE_NAME2:~ --zone europe-west1-b

- gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@NODE_NAME1 --zone europe-west1-b
- bash install_mcperf.sh
- exit

- gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@NODE_NAME2 --zone europe-west1-b
- bash install_mcperf.sh
- exit

Now this is specific to Part 1:

Get the internal IP (MEMCACHED_IP)

- kubectl get pods -o wide
  Find your some-memcached pod. You’ll see a column called IP. (last: 100.96.2.2)

Get the INTERNAL_AGENT_IP for the client-agent (last: 10.0.16.5)

- kubectl get nodes -o wide

SSH into the agent node (don't forget to change the name of the VM)

- gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-agent-ldw5 --zone europe-west1-b
- cd ~/memcache-perf
- ./mcperf -T 8 -A
  KEEP THIS TERMINAL OPEN (it looks like it's stuck but it's running!)

Open a new terminal

Load memcached and start measuring from client-measure (don't forget to change the name of the VM)

- gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-measure-qlzb --zone europe-west1-b
- cd ~/memcache-perf
- ./mcperf -s MEMCACHED_IP --loadonly (replace the IP)

Run the first measurements:

- ./mcperf -s MEMCACHED_IP -a INTERNAL_AGENT_IP \
- --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 \
- --scan 5000:80000:5000

To save results to a csv file in the current folder:
Experiment 1 (baseline):

- ./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > baseline.csv
  Pull result locally (the csv is currently in the VM): don't forget to change the name of the VM
  Run locally:
- gcloud compute scp ubuntu@client-measure-qlzb:~/memcache-perf/file_name.csv ./results/ --zone europe-west1-b

Baseline:
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > baseline_run1.csv

CPU interference:
on laptop
kubectl create -f interference/ibench-cpu.yaml

inside VM:
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > cpu_run1.csv

on laptop
kubectl delete pod ibench-cpu

l1d interference:
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > l1d_run1.csv

l1i interference
kubectl create -f interference/ibench-l1i.yaml
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > l1i_run1.csv
kubectl delete pod ibench-l1i

l2
kubectl create -f interference/ibench-l2.yaml
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > l2_run1.csv
kubectl delete pod ibench-l2

llc
kubectl create -f interference/ibench-llc.yaml
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > llc_run1.csv
kubectl delete pod ibench-llc

membw
kubectl create -f interference/ibench-membw.yaml
./mcperf -s 100.96.2.2 -a 10.0.16.5 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000 > membw_run1.csv
kubectl delete pod ibench-membw

## PART 4: Dynamic Scheduling

How to use and set-up controllerv2.py:

Permissions:
The user running this script must be in the docker group (sudo usermod -aG docker $USER, then log out/in).
taskset usually requires sudo. You might need to run sudo python3 controller.py or configure sudoers for passwordless taskset for the specific user and command if running without full sudo.
Memcached Setup (Part 4 instructions):
Install memcached on the memcache-server-qmql VM.
Configure /etc/memcached.conf:
-m 1024 (memory limit)
-l <internal_IP_of_memcache-server-qmql> (listen address)
You can also add -t 1 or -t 2 for initial software threads, but taskset will control CPU core pinning. It's generally fine to let memcached manage its internal threads if pinned to specific cores.
sudo systemctl restart memcached
sudo systemctl status memcached to verify.
Augmented mcperf Setup (Part 3 instructions):
Install the augmented mcperf on client-agent-bf7q and client-measure-5v6m.
SSH Keys (Recommended for seamless mcperf execution):
Set up passwordless SSH from memcache-server-qmql (where controller runs) to client-measure-5v6m (where mcperf queries are initiated).
Alternative/Simpler mcperf Handling (as implemented in the script):
On the client-measure-5v6m VM, manually run the mcperf command.
Redirect its standard output to a file that is accessible by the memcache-server-qmql VM. This could be an NFS share, or you could periodically scp the output.
The script is currently set up to tail -F a local file MCPERF_OUTPUT_FILE. So, you need to get mcperf's output into this file on the controller's VM.
Example on client-measure VM:

# Assuming memcache-perf-dynamic is in home directory

cd ~/memcache-perf-dynamic

# Replace <CONTROLLER_VM_IP> and <PATH_ON_CONTROLLER_VM>

# This pipes output over SSH to the controller VM, writing to the file.

./mcperf -s <MEMCACHED_SERVER_IP> -a <MCPERF_AGENT_IP> \
 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 300 \
 --qps_interval 2 --qps_min 5000 --qps_max 180000 \
 | ssh <USER>@<CONTROLLER_VM_IP> "cat > /home/<USER>/MCPERF_OUTPUT_FILE_NAME_AS_IN_SCRIPT"
Use code with caution.
Bash
Or, if NFS is set up: ... > /mnt/shared_nfs/mcperf_output_for_controller.txt
Batch Job Docker Images: Ensure the specified Docker images are accessible (e.g., public on Docker Hub or pre-pulled).
Configuration: Update IP addresses and paths at the top of controller.py.
Run the Controller:
Copy controller.py to the memcache-server-qmql VM.
python3 controller.py (or sudo python3 controller.py if needed for taskset).
Output:
controller_execution_log.txt (or your configured name) will contain the job log.
MCPERF_OUTPUT_FILE (e.g., mcperf_controller_run.txt) should contain the raw mcperf output.
Important Considerations & Potential Improvements:

mcperf Output Handling: The current readline() on tail -F's stdout might block if mcperf output is sparse. A more robust solution would use select.select or asyncio for non-blocking I/O on the mcperf_process.stdout file descriptor. For the project's scope, if mcperf updates every 2s (due to qps_interval), this might be acceptable.
CPU Utilization for Memcached Scaling: The script currently scales memcached primarily on SLO. CPU utilization of memcached itself could be a secondary factor (e.g., don't scale down if its own CPU util is high even if SLO is met).
Batch Job Resource Adjustment: The script assigns all available non-memcached cores to a single batch job at launch. It does not dynamically docker update a running batch job's cpuset-cpus. If memcached needs more cores, the current logic doesn't preempt/shrink the running batch job. A more advanced controller might pause the batch job, reconfigure memcached, then resume the batch job on fewer cores or wait.
Robustness: Add more comprehensive error checking and recovery.
Concurrency for Batch Jobs: The current script runs one batch job at a time. If there are many small, independent batch jobs and enough distinct cores, running them concurrently could be more efficient. This would significantly increase controller complexity.
SSH for mcperf: Integrating direct SSH control for mcperf would make the setup more automated but adds complexity (key management, SSH library like paramiko).
This script provides a solid foundation. You'll need to test it thoroughly in the Google Cloud environment and likely tweak parameters and logic based on observed behavior. The mcperf output handling is a key area to ensure works reliably.
