#!/bin/bash

# MEMCACHED and AGENT IPs
MEMCACHED_IP="100.96.2.2"
INTERNAL_AGENT_IP="10.0.16.5"

# Directory to save results
mkdir -p results

# List of benchmarks
BENCHMARKS=("baseline" "cpu" "l1d" "l1i" "l2" "llc" "membw")

# Repeat each experiment 3 times
for bench in "${BENCHMARKS[@]}"
do
  echo "=============================="
  echo "Running benchmark: $bench"
  echo "=============================="

  # If not baseline, launch interference pod
  if [ "$bench" != "baseline" ]; then
    echo "Starting interference: $bench"
    kubectl create -f interference/ibench-${bench}.yaml

    # Wait until pod is ready
    echo "Waiting for interference pod to become ready..."
    kubectl wait --for=condition=Ready pod/ibench-${bench} --timeout=120s
  fi

  # Run 3 times
  for i in 1 2 3
  do
    echo ">>> Run $i for $bench"
    
    ./mcperf -s $MEMCACHED_IP -a $INTERNAL_AGENT_IP \
      --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 \
      --scan 5000:80000:5000 > results/${bench}_run${i}.csv

    echo "Saved: results/${bench}_run${i}.csv"
    sleep 10  # short break between runs
  done

  # If not baseline, kill interference pod
  if [ "$bench" != "baseline" ]; then
    echo "Deleting interference pod: ibench-${bench}"
    kubectl delete pod ibench-${bench}
  fi

  # Wait a bit to let cluster stabilize before next run
  sleep 20
done

echo "✅ All experiments completed."
