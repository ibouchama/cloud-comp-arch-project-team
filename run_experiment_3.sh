#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <run-number (1|2|3)>"
  exit 1
fi
RUN_NUM=$1
GROUP=094
RESULT_DIR="part_3_results_group_${GROUP}"

mkdir -p "${RESULT_DIR}"

# ─── Configuration ─────────────────────────────────────────────────────────────
ZONE="europe-west1-b"
SSH_USER="ubuntu"

# Your GCE instance names (update if yours differ)
CLIENT_AGENT_A="client-agent-a-bvtf"
CLIENT_AGENT_B="client-agent-b-mvxd"
CLIENT_MEASURE="client-measure-vcsx"

# ─── Wait for memcached to be up ─────────────────────────
echo "⏳ Waiting for memcached pod to be Ready…"
kubectl wait --for=condition=Ready pod/some-memcached --timeout=120s

# Auto-detect your memcached service's ClusterIP:
MEMCACHED_IP=$(kubectl get svc some-memcached-11211 -o jsonpath='{.spec.clusterIP}')
echo "✅ Memcached cluster IP: $MEMCACHED_IP"


# Directory containing your 7 batch-job YAMLs
JOBS_MANIFEST_DIR="parsec-benchmarks/part3/"
MC_LOG_LOCAL="mcperf-measure.log"

# ─── Helper to get an instance's internal IP ───────────────────────────────────
get_internal_ip() {
  local instance="$1"
  gcloud compute instances describe "${instance}" \
    --zone="${ZONE}" \
    --format='get(networkInterfaces[0].networkIP)'
}

AGENT_A_IP=$(get_internal_ip "${CLIENT_AGENT_A}")
AGENT_B_IP=$(get_internal_ip "${CLIENT_AGENT_B}")

# ─── 1) Start mcperf on the two agents ─────────────────────────────────────────
echo "Starting mcperf load on ${CLIENT_AGENT_A} (2 threads)…"
gcloud compute ssh "${SSH_USER}@${CLIENT_AGENT_A}" \
  --zone "${ZONE}" \
  --ssh-key-file ~/.ssh/cloud-computing \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -T 2 -A > mcperf-agent-a.log 2>&1 &"

echo "Starting mcperf load on ${CLIENT_AGENT_B} (4 threads)…"
gcloud compute ssh "${SSH_USER}@${CLIENT_AGENT_B}" \
  --zone "${ZONE}" \
  --ssh-key-file ~/.ssh/cloud-computing \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -T 4 -A > mcperf-agent-b.log 2>&1 &"

# ─── 2) Start the measure VM (warm-up  measurement) ──────────────────────────
echo "Warming up on ${CLIENT_MEASURE} (loadonly)…"
gcloud compute ssh "${SSH_USER}@${CLIENT_MEASURE}" \
  --zone "${ZONE}" \
  --ssh-key-file ~/.ssh/cloud-computing \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -s ${MEMCACHED_IP} --loadonly > mcperf-loadonly.log 2>&1 & sleep 5; \
             nohup \$HOME/memcache-perf-dynamic/mcperf \
               -s ${MEMCACHED_IP} \
               -a ${AGENT_A_IP} -a ${AGENT_B_IP} \
               --noload -T 6 -C 4 -D 4 -Q 1000 -c 4 -t 10 \
               --scan 30000:30500:5 \
               > mcperf-measure.log 2>&1 &"

echo "→ Memcached is now under a steady ~30K QPS load with p95 measurements every 10 s."

# ─── 3) Deploy your batch jobs ─────────────────────────────────────────────────
echo "Submitting batch jobs in ${JOBS_MANIFEST_DIR}…"
kubectl apply -f "${JOBS_MANIFEST_DIR}"
echo "→ Batch jobs submitted."

# ─── 4) Wait until every Job finishes (no double‐counting retries) ────
echo "⏳ Waiting for all Jobs to complete (up to 1h)…"
kubectl wait --for=condition=complete job --all --timeout=3600s
echo "→ All batch Jobs completed."

# ─── 5) Retrieve and check mcperf log for SLO violations ─────
echo "📥 Fetch mcperf log from ${CLIENT_MEASURE}…"
gcloud compute scp "${SSH_USER}@${CLIENT_MEASURE}:~/mcperf-measure.log" \
                  "${RESULT_DIR}/mcperf_${RUN_NUM}.txt" \
                  --zone "${ZONE}" --ssh-key-file ~/.ssh/cloud-computing

MC_TXT="${RESULT_DIR}/mcperf_${RUN_NUM}.txt"
echo "🔍 Checking p95 latency SLO (< 1 ms)…"
if grep -qE '95th percentile: [1-9]' "$MC_TXT"; then
  echo "❌ SLO violation: found 95th percentile ≥ 1 ms!"
else
  echo "✅ SLO met: all recorded 95th percentiles < 1 ms"
fi

# ─── 6) Gather timestamps & compute makespan ──────────────────────────────────
echo "Collecting timestamps and computing runtimes:"
kubectl get pods -o json > "${RESULT_DIR}/pods_${RUN_NUM}.json"
echo "⏱ Computing makespan from that JSON…"
# print to console and also tee it into a file makespan_<N>.txt
python3 get_time.py "${RESULT_DIR}/pods_${RUN_NUM}.json" \
  | tee "${RESULT_DIR}/makespan_${RUN_NUM}.txt"
 
echo "✅ Run #${RUN_NUM} results written to"
echo "    • ${RESULT_DIR}/pods_${RUN_NUM}.json"
echo "    • ${RESULT_DIR}/mcperf_${RUN_NUM}.txt"
echo "    • ${RESULT_DIR}/makespan_${RUN_NUM}.txt"

echo "✅ Experiment finished."
