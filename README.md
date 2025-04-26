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

SSH into the agent node

- gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-agent-ldw5 --zone europe-west1-b
- cd ~/memcache-perf
- ./mcperf -T 8 -A
  KEEP THIS TERMINAL OPEN (it looks like it's stuck but it's running!)

Open a new terminal

Load memcached and start measuring from client-measure

- gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-measure-qlzb --zone europe-west1-b
- cd ~/memcache-perf
- ./mcperf -s MEMCACHED_IP --loadonly (replace the IP)

Run the first measurements:

- ./mcperf -s MEMCACHED_IP -a INTERNAL_AGENT_IP \
- --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 \
- --scan 5000:80000:5000

If everything works fine, run the script to make measurements and saves the result to csv files. Replace the IPs in the script before running it.

- gcloud compute scp run_experiments.sh ubuntu@client-measure-qlzb:~/memcache-perf --zone europe-west1-b (replace the client-measure name)

- chmod +x run_experiments.sh
- bash run_experiments.sh
