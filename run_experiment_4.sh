#!/usr/bin/env bash
set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────────────────────
ZONE="europe-west1-b"
SSH_USER="ubuntu"
SSH_KEY="$HOME/.ssh/cloud-computing"    # adjust if needed

# GKE node / GCE instance names
MEMCACHE_NODE="memcache-server-xt2n"
AGENT_INSTANCE="client-agent-8pmq"
MEASURE_INSTANCE="client-measure-s855"

# ─── Discover internal IPs ─────────────────────────────────────────────────────
echo "⏳ Fetching internal IPs…"
MEMCACHED_IP=$(kubectl get nodes -o jsonpath="{.items[?(@.metadata.name=='${MEMCACHE_NODE}')].status.addresses[?(@.type=='InternalIP')].address}")
AGENT_IP=$(kubectl get nodes -o jsonpath="{.items[?(@.metadata.name=='${AGENT_INSTANCE}')].status.addresses[?(@.type=='InternalIP')].address}")

echo " • memcached: $MEMCACHED_IP"
echo " • agent VM:  $AGENT_IP"

# ─── 1) Launch the agent on client-agent-8pmq ─────────────────────────────────
echo "🚀 Starting mcperf agent (8 threads)…"
gcloud compute ssh "${SSH_USER}@${AGENT_INSTANCE}" \
  --zone "${ZONE}" \
  --ssh-key-file "${SSH_KEY}" \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -T 8 -A > mcperf-agent.log 2>&1 &"

# ─── 2) Pre-load the cache on client-measure-s855 ──────────────────────────────
echo "⚙️  Pre-loading key-value pairs…"
gcloud compute ssh "${SSH_USER}@${MEASURE_INSTANCE}" \
  --zone "${ZONE}" \
  --ssh-key-file "${SSH_KEY}" \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -s ${MEMCACHED_IP} --loadonly > mcperf-loadonly.log 2>&1 & sleep 5"

# ─── 3) Run dynamic-QPS test on client-measure-s855 ────────────────────────────
echo "🎯 Running dynamic load (2s intervals, 5k–180k QPS, 10s total)…"
gcloud compute ssh "${SSH_USER}@${MEASURE_INSTANCE}" \
  --zone "${ZONE}" \
  --ssh-key-file "${SSH_KEY}" \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf \
    -s ${MEMCACHED_IP} \
    -a ${AGENT_IP} \
    --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 10 \
    --qps_interval 2 --qps_min 5000 --qps_max 180000 \
    > mcperf-measure.log 2>&1 &"

echo "✅ Done!  
 • Agent logs:    mcperf-agent.log on ${AGENT_INSTANCE}  
 • Measure logs:  mcperf-loadonly.log & mcperf-measure.log on ${MEASURE_INSTANCE}"
#todo: check why no log files.
