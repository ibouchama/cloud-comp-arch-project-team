#!/usr/bin/env bash
set -euo pipefail

# ===============================================================================
# run_part2b_baseline_3x_avg.sh
#
# Runs each PARSEC Part2b job 3× for thread counts 1, 2, 4, and 8,
# computes the average 'real' time across runs,
# and writes per-run logs plus a per-job per-thread average.
#
# Usage:
#   chmod +x run_part2b_baseline_3x_avg.sh
#   ./run_part2b_baseline_3x_avg.sh
#
# Prerequisites:
#   • kubectl context set to part2b.k8s.local
#   • parsec-benchmarks/part2b/*.yaml present
# ===============================================================================

LOG_ROOT="results2b_baseline_3x_avg"
JOB_DIR="parsec-benchmarks/part2b"
THREAD_COUNTS=(1 2 4 8)
threads=4

echo "Using kubectl context: $(kubectl config current-context)"

  LOG_DIR="$LOG_ROOT/${threads}threads"
  mkdir -p "$LOG_DIR"
  echo
  echo "=== Running benchmarks with ${threads} threads ==="

  for yaml in "$JOB_DIR"/*.yaml; do
    job_name=$(basename "$yaml" .yaml)
    sum=0
    echo
    echo "-- Benchmark: ${job_name} (threads=${threads}) --"

    for run in 1 2 3; do
      echo "-> Run #${run}"

      # teardown any old job
      kubectl delete job "$job_name" --ignore-not-found

      # launch the job with overridden thread count
      kubectl create -f <(sed -E "s/(-n )[0-9]+/\\1${threads}/" "$yaml")
      kubectl wait --for=condition=complete job/"$job_name" --timeout=600s

      # get pod name and collect logs
      pod=$(kubectl get pods --selector=job-name="$job_name" --output=jsonpath='{.items[*].metadata.name}')
      out="$LOG_DIR/${job_name}_t${threads}_run${run}.log"
      echo "   logs → $out"
      kubectl logs "$pod" > "$out"

      # parse 'real' time
      real_line=$(grep '^real' "$out")
      min=$(echo "$real_line" | awk '{split($2, a, "m"); print a[1]}')
      sec=$(echo "$real_line" | awk '{split($2, a, "m"); print a[2]}' | sed 's/s//')
      echo "   min =${min} \n   sec =${sec}"
      real_sec=$(awk -v min="$min" -v sec="$sec" 'BEGIN { printf "%.3f", min*60 + sec }')
      echo "   real_time = ${real_sec}s"
      sum=$(awk -v sum="$sum" -v real_sec="$real_sec" 'BEGIN {print sum + real_sec}')
      echo "   sum=${sum}"

      # cleanup
      kubectl delete job "$job_name" --ignore-not-found
    done

    # compute average
    avg=$(awk -v sum="$sum" 'BEGIN {printf "%.3f", sum/3}')
    summary="$LOG_DIR/${job_name}_t${threads}_baseline_avg.txt"
    echo "$avg" | tee "$summary"
    echo ">>> ${job_name} (threads=${threads}) avg = ${avg}s"
  done

echo
 echo "✅ All Part2b baseline runs done; logs and averages in $LOG_ROOT/*"

