#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <run-number (1|2|3)>"
  exit 1
fi
RUN_NUM=$1
GROUP=094
RESULT_DIR="part_4.2_t2c2"
mkdir -p "${RESULT_DIR}"

# ─── Test parameters ───────────────────────────────────────────────────────────
# run mcperf for this many seconds (must be ≥ 60)
MCperf_DURATION=1200 # 20 minutes  
IDLE_AFTER=60       # seconds of idle memcached

# ─── Configuration ─────────────────────────────────────────────────────────────
ZONE="europe-west1-b"
SSH_USER="ubuntu"

# VM names
MEMCACHE_VM="memcache-server-9sh9"
CLIENT_AGENT_VM="client-agent-qvzc"
CLIENT_MEASURE_VM="client-measure-35qn"

# ─── Helper to get internal IP ──────────────────────────────────────────────────
get_ip() {
  local vm=$1
  gcloud compute instances describe "$vm" \
    --zone="$ZONE" \
    --format='get(networkInterfaces[0].networkIP)'
}

MEMCACHED_IP=$(get_ip "$MEMCACHE_VM")
AGENT_IP=$(get_ip "$CLIENT_AGENT_VM")

echo "Configuration:"
echo "  Memcached VM:    $MEMCACHE_VM -> $MEMCACHED_IP"
echo "  Client Agent VM: $CLIENT_AGENT_VM -> $AGENT_IP"
echo "  Measure VM:      $CLIENT_MEASURE_VM"

echo -e "\n=== 1) Launch mcperf agent on $CLIENT_AGENT_VM ==="
gcloud compute ssh "${SSH_USER}@${CLIENT_AGENT_VM}" \
  --zone "$ZONE" \
  --ssh-key-file ~/.ssh/cloud-computing \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -T 8 -A > mcperf-agent-a.log 2>&1 &"

echo -e "\n=== 2) Run dynamic load on $CLIENT_MEASURE_VM ==="
gcloud compute ssh "${SSH_USER}@${CLIENT_MEASURE_VM}" \
  --zone "$ZONE" \
  --ssh-key-file ~/.ssh/cloud-computing \
  -- bash -s <<EOF | tee "${RESULT_DIR}/mcperf_${RUN_NUM}.txt"
cd ~/memcache-perf-dynamic

# preload
./mcperf -s ${MEMCACHED_IP} --loadonly

START_TS=\$(date +%s)
echo "\$(date +%T)  Starting mcperf load (duration=${MCperf_DURATION}s)"

# do the dynamic load
./mcperf \
  -s ${MEMCACHED_IP} \
  -a ${AGENT_IP} \
  --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 \
  -t ${MCperf_DURATION} \
  --qps_interval 10 --qps_min 5000 --qps_max 180000

END_TS=\$(date +%s)
echo "\$(date +%T)  Finished load. Elapsed: \$(( END_TS - START_TS ))s"

# now guarantee 1 minute of “running alone”
echo "\$(date +%T)  Sleeping ${IDLE_AFTER}s to let memcached run alone…"
sleep ${IDLE_AFTER}
echo "\$(date +%T)  Running-alone window complete."
EOF
