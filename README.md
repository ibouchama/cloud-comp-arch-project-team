To set-up the environment, create a new bucket and a new cluster within, run the following instructions:

- source env_setup.sh
- bash create_bucket.sh
- gcloud auth login
- gcloud auth application-default login
- `bash create_cluster.sh` (or `bash create_cluster_2a.sh` for part2a)

If you see the following retry on the terminal:
```
W0429 17:21:27.764283    9716 validate_cluster.go:182] (will retry): unexpected error during validation: error listing nodes: Get "https://34.79.80.180/api/v1/nodes": dial tcp 34.79.80.180:443: connect: connection refused
```
Then it's normal. Those retries aren’t a new error so much as the script `create_cluster.sh` polling the API server before it’s up. On GCE it can easily take 5–10 minutes from the time you run `kops update cluster … --yes` until:
1. The master VM is fully booted
2. kube-apiserver comes up
3. The GCE load-balancer / forwarding rule becomes healthy
4. The TLS certs are in place

Only then will
```
kops validate cluster --name part2a.k8s.local --wait 10m
```
actually see your node(s) and return success. Until that point you’ll continue to see connect: connection refused or timeouts.

During the time of waiting these retries, we can watch it manually. In another terminal, run:
```
kubectl get nodes --context part2a.k8s.local --watch
```
Once you see your master (and parsec-server node) transition to `Ready`, our `validate` will succeed immediately.

After the API server is healthy, kops validate will stop retrying and report your cluster as ready.

\
  If you encounter an error when `bash create_cluster.sh`, try the following set of commands:
- gcloud auth login
- gcloud auth application-default login
- source env_setup.sh
- export PROJECT=$(gcloud config get-value project)
- export KOPS_STATE_STORE=gs://cca-eth-2025-group-94-ibouchama/

Your cluster should now be created. Verify with the following command and get the names of the vms:

- `kubectl get nodes -o wide`
  You should see 4 nodes: 1 master and 3 nodes\
  8 nodes for 

\
Please go to section Part2a if you're doing Part2a. Otherwise, continue.

\
To launch memcached, run this:

- bash launch_memcached.sh

\
Please go to section Part3 if you're doing Part3. Otherwise, continue.

\
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

# Part1
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


\
IMPORTANT: you must delete your cluster when you are not using it! Otherwise, you will easily use up all of your cloud credits! When you are ready to work on the project, you can easily re-launch the cluster with the instructions above. To delete your cluster, use the command:
```
kops delete cluster part1.k8s.local --yes
```

# Part2a
Do the same thing as above up to (included)
```
kubectl get nodes -o wide
```
You should see 2 nodes: 1 master and 1 node

Then connect to the `parsec-server` VM using gcloud:
```
gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@parsec-server-xxxx --zone europe-west1-b
```

And now, you're in the `parsec-server` VM!

\
Please change the nodetype from `memcached` to `parsec` for each interference type in `interference/` directory, i.e.
```
  nodeSelector:
    cca-project-nodetype: "parsec"
    # cca-project-nodetype: "memcached"
```

\
In another terminal of your laptop (in the same directory where you did your `git clone` of the repo and sourced `env_setup.sh`), make sure that the jobs can be scheduled successfully, run the following command in order to
assign the appropriate label to the parsec node `kubectl label nodes parsec-server-xxxx cca-project-nodetype=parsec`

If encountering `node/parsec-server-xxxx not labeled` as output,
Then
1. `kubectl config current-context`
2. `kubectl get nodes`
3. `kubectl label node parsec-server-xxxx cca-project-nodetype=parsec`
4. `kubectl get node parsec-server-xxxx --show-labels`
If you get the output
```
NAME                 STATUS   ROLES   AGE   VERSION   LABELS
parsec-server-xxxx   Ready    node    39m   v1.31.5   beta.kubernetes.io/arch=amd64,beta.kubernetes.io/instance-type=n2-standard-2,beta.kubernetes.io/os=linux,cca-project-nodetype=parsec,cloud.google.com/metadata-proxy-ready=true,failure-domain.beta.kubernetes.io/region=europe-west1,failure-domain.beta.kubernetes.io/zone=europe-west1-b,kops.k8s.io/instancegroup=nodes-europe-west1-b,kubernetes.io/arch=amd64,kubernetes.io/hostname=parsec-server-xxxx,kubernetes.io/os=linux,node-role.kubernetes.io/node=,node.kubernetes.io/instance-type=n2-standard-2,topology.gke.io/zone=europe-west1-b,topology.kubernetes.io/region=europe-west1,topology.kubernetes.io/zone=europe-west1-b
```

Then it simply means: all that “not labeled” noise is just kubectl telling you “no change” — the label was already there (kops applied it for you from your `nodeLabels`: stanza). 
So everything is fine.

\
Then
```
kubectl create -f interference/ibench-cpu.yaml # Wait for interference to start
kubectl create -f parsec-benchmarks/part2a/parsec-dedup.yaml
```

\
Then execute each interference type (cpu l1d l1i l2 llc membw) and for each PARSEC Part2a's script in order to compute the interference_type_3times_avg
```
chmod +x run_part2a_all_interference_3x_avg.sh
./run_part2a_all_interference_3x_avg.sh
```
The averages are in `results2a_interferences_3x` folder.

\
Then execute the baseline script to compute the baseline_3times_avg
```
chmod +x run_part2a_baseline_3x_avg.sh
./run_part2a_baseline_3x_avg.sh
```
Each run's baseline (`real`) value is in `results2a_baseline_3x_avg` folder.

\
Finally, the computation result is in `result2a_my_computation_for_avg.txt` .

Last but not least, DELETE THE CLUSTER!!!!!!
```
kops delete cluster part2a.k8s.local --yes
```

## Note:
difference between
```
pod=$(kubectl get pods -l job-name="$job_name" -o jsonpath='{.items[0].metadata.name}')
```
and
```
pod=$(kubectl get pods --selector=job-name="$job_name" --output=jsonpath='{.items[*].metadata.name}')
```

1. Selector syntax:
`-l job-name="$job_name"` is just shorthand for `--selector=job-name="$job_name"`, so no difference.
2. JSONPath expression:\
A Pod here is the things that we delete every time before and after each iteration.\
- `'{.items[0].metadata.name}'` picks only the first Pod in the returned list.\
- `'{.items[*].metadata.name}'` walks every item and spits out all Pod names (space-separated).\
If your Job only ever spins up one Pod, you’ll see the same thing either way. But if there are ever multiple matching Pods (e.g. you forgot to delete an old one, or parallelism >1), then:\
- `[0]` → you get a single name (the first).\
- `[*]` → you get all of them.\
So pick `[0]` if you’re certain there’s just one Pod you care about, or `[*]` if you really want a list of all of them.


# Part3
Goal of part3: **Co-schedule** the latency-critical memcached application from Part 1 and all seven batch applications from Part 2 in a heterogeneous cluster, consisting of VMs with a different number of
cores.

\
To install the augmented version of mcperf on `client-agent-*` and `client-measure`, do
```
bash install_mcperf_3.sh
```

Based on `kubectl get nodes -o wide`,
- in each yaml file, change the node name.
- in run_experiment_3.sh, change the agents and the client name.

\
Every time we change things in `memcache-t1-cpuset.yaml`, we need to do:
```
kubectl delete pod some-memcached         # tear down the old one
kubectl apply  -f memcache-t1-cpuset.yaml # bring up the new spec
```
if unable, then we can do a “replace” which under the hood deletes and recreates for us:
```
kubectl replace --force -f memcache-t1-cpuset.yaml
```

After doing all these, do:
In `run_experiment_3.sh`,
Replace the node name and the agents name.

Run the scheduling policy bash script:
```
chmod +x run_experiment_3.sh
./run_experiment_3.sh
```

\
In another terminal, we can

- Verify which pods are still active:
```
kubectl get pods
```
Running →  the container is running.\
Completed → the container ran to completion (exit code 0).\
Error → the container exited non-zero before finishing.\
OOMKilled → the kubelet forcibly killed the container because it exceeded the node’s available memory.

Eg:
```
kubectl get pods
NAME                        READY   STATUS      RESTARTS   AGE
parsec-blackscholes-8vpg8   0/1     Completed   0          25m
parsec-canneal-g2278        0/1     Completed   0          25m
parsec-dedup-5dgrp          0/1     Completed   0          25m
parsec-ferret-q2dzw         0/1     Completed   0          25m
parsec-freqmine-7wz4j       0/1     Completed   0          25m
parsec-radix-cqzs2          0/1     Completed   0          25m
parsec-vips-7d5g6           0/1     Completed   0          25m
some-memcached              1/1     Running     0          71m
```

- Debug stuck pods:
If you think they’ve hung or failed to schedule, pick one of the pod names and run:
```
kubectl describe pod <that-pod-name>
kubectl logs <that-pod-name>
```
in order to see events, resource-insufficiency messages, or crash logs.

\
Remember, before each `./run_experiment_3.sh`, on another terminal, always do
```
kubectl delete jobs --all
```
if unable to delete a job, then force to delete
```
kubectl delete pod <that-pod-name> --grace-period=0 --force
```
Eg:
```
kubectl delete pod parsec-canneal-vnxdr --grace-period=0 --force
```

And check again if all jobs are deleted:
```
kubectl get pods
```

\
The output is stored in `results.json` .

Please refer to `output_3.txt` to see the printed stuff of run_experiment_3.sh and things on the other terminal


## In the yaml files:

I've modified `memcache-t1-cpuset.yaml` and created 7 yaml files under `parsec-benchmarks/part3/`.

| Label key                       | Exists by default? | How to use                     |
| ------------------------------- | ------------------ | ------------------------------ |
| `kubernetes.io/hostname`        | ✅ yes              | No setup. Select on node name. |
| `cca-project-nodetype` (custom) | ❌ no               | First `kubectl label node …`   |


\
Finally, the computation result is in `result2a_my_computation_for_avg.txt` .

Last but not least, DELETE THE CLUSTER!!!!!!
```
kops delete cluster part3.k8s.local --yes
```

