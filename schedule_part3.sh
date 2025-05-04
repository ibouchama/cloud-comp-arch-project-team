#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# schedule_part3.sh
# -----------------------------------------------------------------------------

# 1) YOUR FOUR WORKER NODES (from `kubectl get nodes -o wide`)
NODE_A="node-a-2core-g5zr"   # e2-highmem-2
NODE_B="node-b-2core-d94v"   # n2-highcpu-2
NODE_C="node-c-4core-g8b2"   # c3-highcpu-4
NODE_D="node-d-4core-fds6"   # n2-standard-4

# 2) LABEL THEM
echo "🔖 Labeling workers…"
kubectl label node "$NODE_A" node-type=node-a-2core --overwrite
kubectl label node "$NODE_B" node-type=node-b-2core --overwrite
kubectl label node "$NODE_C" node-type=node-c-4core --overwrite
kubectl label node "$NODE_D" node-type=node-d-4core --overwrite

# 3) DEPLOY MEMCACHED
echo; echo "📦 Deploying memcached on $NODE_A…"
kubectl delete pod some-memcached --ignore-not-found
kubectl create -f memcache-t1-cpuset.yaml

echo "🛡 Exposing as LoadBalancer…"
kubectl delete svc some-memcached-11211 --ignore-not-found
kubectl expose pod some-memcached \
    --name some-memcached-11211 \
    --type LoadBalancer --port 11211 --protocol TCP

echo "⏱ Waiting 60s for external IP…"
sleep 60

MEMCACHED_IP=$(kubectl get svc some-memcached-11211 \
  -o jsonpath='{.spec.clusterIP}')
echo "✅ Memcached LB IP: $MEMCACHED_IP"

# 4) START mcperf AGENTS ON YOUR VMs
AGENT1="client-agent-a-zrh1"
AGENT2="client-agent-b-cw94"
MEASURE="client-measure-lnw5"

declare -a pids
for AG in "$AGENT1" "$AGENT2"; do
  if [[ "$AG" == "$AGENT1" ]]; then
    THREADS=2
  else
    THREADS=4
  fi

  echo; echo "🚀 Launching mcperf agent on $AG (threads=$THREADS)…"
  gcloud compute scp install_mcperf.sh ubuntu@"$AG":~ --zone europe-west1-b
  gcloud compute ssh ubuntu@"$AG" --zone europe-west1-b \
    --ssh-key-file ~/.ssh/cloud-computing --command "\
      bash ~/install_mcperf.sh && \
      nohup ~/memcache-perf/mcperf -T $THREADS -A \
        > ~/mcperf-agent.log 2>&1 & \
      exit
    " &
  pids+=("$!")
done

echo; echo "Spawned SSH jobs for agents: ${pids[*]}"
jobs -l
echo "Waiting for all agent SSH sessions to exit…"
wait "${pids[@]}"
echo "✅ All mcperf agents are up."

# 5) START THE MEASURING CLIENT (backgrounded locally)
echo; echo "🎯 Launching mcperf measuring client on $MEASURE…"
gcloud compute scp install_mcperf.sh ubuntu@"$MEASURE":~ --zone europe-west1-b
gcloud compute ssh ubuntu@"$MEASURE" --zone europe-west1-b \
  --ssh-key-file ~/.ssh/cloud-computing --command "\
    bash ~/install_mcperf.sh && \
    ~/memcache-perf/mcperf -s $MEMCACHED_IP --loadonly && \
    nohup ~/memcache-perf/mcperf -s $MEMCACHED_IP \
      -a $MEMCACHED_IP -T 6 -C 4 -D 4 -Q 1000 -c 4 -t 10 \
      --scan 30000:30500:5 \
      > ~/mcperf-measure.log 2>&1 & \
    exit
  " &

echo "✅ Measure client SSH spawned."

# 6) SCHEDULE THE 7 PARSEC JOBS
PARSEC_DIR="parsec-benchmarks/part3"
RESULTS="results3"
mkdir -p "$RESULTS"

declare -A NODE_FOR=(
  [blackscholes]=any
  [canneal]=node-b-2core
  [dedup]=any
  [ferret]=node-a-2core
  [freqmine]=any
  [radix]=any
  [vips]=any
)

echo; echo "📋 Launching PARSEC jobs…"
for wl in "${!NODE_FOR[@]}"; do
  job="parsec-$wl"

  # tear down any old run
  kubectl delete job "$job" --ignore-not-found
  kubectl delete pods --selector=job-name="$job" --ignore-not-found

  if [[ "${NODE_FOR[$wl]}" == "any" ]]; then
    kubectl create -f "$PARSEC_DIR/$job.yaml"
  else
    # inject nodeSelector with sed
    kubectl create -f "$PARSEC_DIR/$job.yaml" --dry-run=client -o yaml \
      | sed "/^  template:/a\      nodeSelector:\n        node-type: ${NODE_FOR[$wl]}" \
      | kubectl apply -f -
  fi
done

echo; echo "⏳ Waiting for PARSEC jobs to complete…"
for wl in "${!NODE_FOR[@]}"; do
  job="parsec-$wl"
  kubectl wait --for=condition=complete job/"$job" --timeout=1200s
  pod=$(kubectl get pods -l job-name="$job" \
        -o jsonpath='{.items[0].metadata.name}')
  kubectl logs "$pod" > "$RESULTS/$job.log"
  echo "  → $job finished, logs in $RESULTS/$job.log"
done

echo; echo "🏁 All done! Results under $RESULTS/"
