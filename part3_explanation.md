Thought for a couple of seconds


In Part 3 you’re **co-scheduling** everything together on the same cluster, so yes—you run memcached and all seven batch workloads at the same time (or in whatever overlap your policy dictates), with two hard requirements:

1. **Memcached must be running continuously under a steady 30 000 QPS load**, and its 95th-percentile tail-latency must never exceed 1 ms.
2. **All seven batch jobs must eventually complete** (using the native dataset), and your policy should drive their *makespan* (time from the moment the first batch job starts until the last one finishes) as low as possible.

---

### Step-by-step workflow

1. **Bring up memcached first**

   * Deploy the memcached Pod (with your pinning, resource requests, affinities, etc.).
   * Expose it as a Service and wait for its external (or cluster) IP.
   * Fire up your two mcperf agents and the mcperf-measure client to hammer 30 K QPS and report tail-latency every 10 s.

2. **While memcached is under load, submit your batch jobs**

   * Use `kubectl apply -f parsec-*.yaml` (or your orchestrator script) to launch all 7 PARSEC jobs.
   * They will queue up or run immediately depending on your nodeSelectors, affinities, resource requests, and the current free capacity on each node.

3. **Monitor and measure**

   * mcperf keeps running in the background, continually checking that p95 < 1 ms.
   * Kubernetes runs your batch Pods on the nodes you’ve chosen (e.g. some on 2-core machines, others on 4-core machines, with any pinning/affinity/anti-affinity rules).

4. **When the last batch job finishes**, collect timestamps (via `kubectl get pods -o json` + `get_time.py`) and compute the total makespan.

---

### Why overlap them?

* **Real-world analogy**: You’ve got a super-latency-sensitive service (memcached) that must stay snappy, *plus* a bunch of heavy background work. In production you’d want to run those background jobs *while* the service is live—but you can’t let them slow it down or starve it of CPU/memory.
* **Part 1 taught you** memcached’s tail-latency behavior under load.
* **Part 2 taught you** the scaling, runtime, and resource profiles of each batch job.
* **Part 3 is the challenge**: use that knowledge to *co-schedule* them optimally, squeezing maximum throughput out of the machines without ever breaking memcached’s 1 ms SLO.

So yes—it’s all running at once (memcached + 7 batch jobs), but arranged so that memcached stays fast and the batch jobs finish as quickly as possible.



---



Here’s a **written mind-map** to help you approach **Part 3** strategically, with clear guidance on when and how to refer to **Part 1 and Part 2**.

---

### 🧠 **Core Objective (Central Node)**:

> **Design a scheduling policy** that:

* ✅ Minimizes **makespan** (completion time) of all batch jobs
* ✅ Meets **Memcached's SLO**: **95th percentile < 1 ms** at **30K QPS**
* ✅ Ensures **no batch job fails** (e.g., due to OOM)
* ✅ Fully utilizes the cluster **at all times**

---

### 🛠️ **Cluster Constraints**

* 4 heterogeneous worker nodes:

  * `node-a-2core`: e2-highmem-2 → **high memory, low CPU**
  * `node-b-2core`: n2-highcpu-2 → **high CPU, low memory**
  * `node-c-4core`: c3-highcpu-4 → **fast CPU, medium memory**
  * `node-d-4core`: n2-standard-4 → **balanced CPU/memory**
* Kubernetes mechanisms allowed: `nodeAffinity`, `resourceRequests`, `limits`, `taskset`, etc.
* Batch workloads use **native dataset**
* Memcached must be **always running** under **30K QPS steady load**

---

### 🔍 **Referring to Part 1 (Memcached Interference Analysis)**

**Use Part 1 to:**

* 🧠 **Identify resource sensitivity of memcached**

  * Which interference types (CPU, memory bandwidth, LLC, etc.) **increase tail latency**?
* 🧮 **Understand the node types that provide stable performance for memcached**

  * Use this to **pin memcached** on a node with **low interference** and sufficient memory
* 💡 Example insight:

  * If memcached is **sensitive to cache or memory bandwidth**, avoid collocating it with cache-hungry batch jobs (from Part 2)

---

### 🔍 **Referring to Part 2 (Batch Jobs Analysis)**

**Use Part 2 to:**

* 📈 Evaluate **speedup curves** for each batch job (e.g., linear, sublinear, no speedup)

  * Helps choose **degree of parallelism** (e.g., don't give 4 cores to a job that doesn’t scale past 2)
* 🧬 Analyze **sensitivity to interference**

  * Avoid collocating sensitive jobs with memcached or other aggressive jobs
* 🗃️ Understand **resource footprint** (memory, CPU)

  * Prevent OOM failures or CPU oversubscription
* 🔁 Decide **job grouping**:

  * Batch jobs with **short runtime** and **low interference** can be safely collocated

---

### 📋 **Scheduling Policy Design Considerations**

**I. Memcached Placement (High Priority)**

* ⚖️ Tradeoff: Need **low-interference**, **stable** node
* 💭 Likely best on `node-a-2core` (highmem) or `node-c-4core` (fast CPU)
* ⛔ Avoid noisy neighbors: don’t collocate with dedup, canneal, freqmine (if they caused latency spikes)

**II. Job Placement & Parallelism**

* 🔍 For each batch job:

  * Set **core count** based on **speedup results**
  * Match with **VM type** based on:

    * CPU scaling needs
    * Memory usage
    * Interference potential

**III. Job Scheduling Order**

* ⏱️ Prioritize long jobs early (if not too noisy)
* 🧵 Run multiple light-parallelism jobs simultaneously
* 🔁 Use backfilling: as soon as cores free up, launch small jobs

**IV. Collocation Strategy**

* 🧮 Consider combining:

  * Low interference + short jobs (e.g., blackscholes, radix)
  * Avoid running multiple memory-hungry or CPU-hungry jobs together

**V. Monitoring and Metrics**

* 🎯 Track:

  * `kubectl get pods -o json` for job runtime
  * `mcperf` output for SLO compliance
* ⛔ Abort or reschedule on signs of SLO violations or failures

---

### 🧰 Tools and Techniques

* **Pinning memcached** to CPU cores using `taskset`
* **Controlling scheduling** with `nodeAffinity`, `tolerations`, `labels`
* **Set resource requests/limits** for batch jobs
* Use automation scripts to:

  * Launch jobs sequentially/in parallel
  * Collect logs for analysis
  * Parse latency and completion time

---

Would you like me to turn this into a diagram or help with a decision tree for job placement?