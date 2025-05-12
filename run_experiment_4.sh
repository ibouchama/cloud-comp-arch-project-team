#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <run-number (1|2|3)>"
  exit 1
fi
RUN_NUM=$1
GROUP=094
RESULT_DIR="part_4_results_group_${GROUP}"
mkdir -p "${RESULT_DIR}"

# ─── Configuration ─────────────────────────────────────────────────────────────
ZONE="europe-west1-b"
SSH_USER="ubuntu"

# VM names
MEMCACHE_VM="memcache-server-cgvn"
CLIENT_AGENT_VM="client-agent-wmf6"
CLIENT_MEASURE_VM="client-measure-21z7"

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
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -s ${MEMCACHED_IP} --loadonly > mcperf-loadonly.log 2>&1 & sleep 5; \
             nohup \$HOME/memcache-perf-dynamic/mcperf \
               -s ${MEMCACHED_IP} \
               -a ${AGENT_IP} \
               --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 10 \
               --qps_interval 2 --qps_min 5000 --qps_max 180000 && 
               > mcperf-measure.log 2>&1 &"

echo -e "\n✅ Run #${RUN_NUM} complete. Results stored in ${RESULT_DIR}/"
