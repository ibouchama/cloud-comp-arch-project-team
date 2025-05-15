#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <run-number (1|2|3)>"
  exit 1
fi
RUN_NUM=$1
GROUP=094
RESULT_DIR="part_4_3_results_group_${GROUP}"
mkdir -p "${RESULT_DIR}"

# ─── Configuration ─────────────────────────────────────────────────────────────
ZONE="europe-west1-b"
SSH_USER="ubuntu"

# VM names
MEMCACHE_VM="memcache-server-74hk"
CLIENT_AGENT_VM="client-agent-rd9r"
CLIENT_MEASURE_VM="client-measure-5m6r"

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

echo "=== 1) Launch scheduler on ${MEMCACHE_VM} ==="
gcloud compute ssh "${SSH_USER}@${MEMCACHE_VM}" \
  --zone="$ZONE" \
  --ssh-key-file ~/.ssh/cloud-computing \
   --command "bash -lc '
    # clean up any old scheduler containers and code (even root-owned files!)
    sudo docker ps -a --filter label=scheduler=true -q | xargs -r sudo docker rm -f
    sudo rm -rf ~/controller

    # grab fresh copy
    git clone -b part4 https://github.com/ibouchama/cloud-comp-arch-project-team.git ~/controller
    cd ~/controller
    git rev-parse --abbrev-ref HEAD
    git rev-parse --short HEAD

    # ensure results directory exists
    mkdir -p ${RESULT_DIR}

    # tell controller.py where to write its jobs log
    export JOBS_LOG=\$PWD/${RESULT_DIR}/jobs_${RUN_NUM}.txt

    # start the scheduler AS ubuntu (no sudo)
    nohup sudo -E python3 controller.py > controller.log 2>&1 &
   '"

echo -e "\n=== 2) Launch mcperf agent on $CLIENT_AGENT_VM ==="
gcloud compute ssh "${SSH_USER}@${CLIENT_AGENT_VM}" \
  --zone "$ZONE" \
  --ssh-key-file ~/.ssh/cloud-computing \
  --command "nohup \$HOME/memcache-perf-dynamic/mcperf -T 8 -A > mcperf-agent-a.log 2>&1 &"

echo -e "\n=== 3) Run dynamic load on $CLIENT_MEASURE_VM ==="
gcloud compute ssh "${SSH_USER}@${CLIENT_MEASURE_VM}" \
  --zone "$ZONE" \
  --ssh-key-file ~/.ssh/cloud-computing \
   --command "bash -lc '
     cd ~/memcache-perf-dynamic
     ./mcperf -s ${MEMCACHED_IP} --loadonly

    START_TS=\$(date +%s%3N)
    echo \"Timestamp start: \$START_TS\"

     ./mcperf \
       -s ${MEMCACHED_IP} \
       -a ${AGENT_IP} \
       --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 10 \
       --qps_interval 10 --qps_min 5000 --qps_max 180000 \
       --qps_seed 2333

    END_TS=\$(date +%s%3N)
    echo \"Timestamp end: \$END_TS\"
  '" | tee "${RESULT_DIR}/mcperf_${RUN_NUM}.txt"


echo "=== 4) Waiting for scheduler to finish ==="
# Poll every 10s until the remote jobs file exists (timeout after 20m)
TIMEOUT=$((20*60/10))  # number of 10s intervals in 20m
count=0
until gcloud compute ssh "${SSH_USER}@${MEMCACHE_VM}" \
    --zone="$ZONE" \
    --ssh-key-file ~/.ssh/cloud-computing \
    --command "test -f ~/controller/${RESULT_DIR}/jobs_${RUN_NUM}.txt" \
    &> /dev/null
do
  ((count++))
  if (( count >= TIMEOUT )); then
    echo "ERROR: timed out waiting for jobs_${RUN_NUM}.txt"; exit 1
  fi
  echo "  still waiting…"
  sleep 10
done

echo "=== 5) Copy scheduler log back ==="
gcloud compute scp \
  "${SSH_USER}@${MEMCACHE_VM}:~/controller/${RESULT_DIR}/jobs_${RUN_NUM}.txt" \
  "${RESULT_DIR}/jobs_${RUN_NUM}.txt" \
  --zone "$ZONE"

gcloud compute scp \
  "${SSH_USER}@${MEMCACHE_VM}:~/controller/controller.log" \
  "${RESULT_DIR}/controller_${RUN_NUM}.log" \
  --zone "$ZONE"

echo "All done! Results in $RESULT_DIR/"