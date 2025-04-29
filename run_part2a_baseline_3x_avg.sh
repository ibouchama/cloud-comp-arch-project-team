#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# run_part2a_baseline_3x_avg.sh
#
# Runs each PARSEC Part2a job 3× with no interference,
# computes the average 'real' time across runs,
# and writes per-run logs plus a per-job average.
#
# Usage:
#   chmod +x run_part2a_baseline_3x_avg.sh
#   ./run_part2a_baseline_3x_avg.sh
#
# Prerequisites:
#   • kubectl context set to part2a.k8s.local
#   • parsec-benchmarks/part2a/*.yaml present
# ==============================================================================

LOG_DIR="results2a_baseline_3x_avg"
mkdir -p "$LOG_DIR"
JOB_DIR="parsec-benchmarks/part2a"

echo "Using kubectl context: $(kubectl config current-context)"

for yaml in "$JOB_DIR"/*.yaml; do
  job_name=$(basename "$yaml" .yaml)
  sum=0

  echo
  echo "=== Baseline 3× for $job_name ==="

  for run in 1 2 3; do
    echo "-> Run #$run"

    # teardown any old job
    kubectl delete job "$job_name" --ignore-not-found

    # launch the job
    kubectl create -f "$yaml"
    kubectl wait --for=condition=complete job/"$job_name" --timeout=600s

    # get pod and collect logs
    pod=$(kubectl get pods --selector=job-name="$job_name" --output=jsonpath='{.items[*].metadata.name}')
    out="$LOG_DIR/${job_name}_run${run}.log"
    echo "   logs → $out"
    kubectl logs "$pod" > "$out"

    # parse 'real' line
    real_line=$(grep '^real' "$out")
    read min sec <<< $(echo "$real_line" | sed -E 's/real\s+([0-9]+)m([0-9.]+)s/\1 \2/')
    real_sec=$(awk "BEGIN {printf \"%.3f\", \$min*60 + \$sec}")
    echo "   real_time = ${real_sec}s"
    sum=$(awk "BEGIN {printf \"%.3f\", $sum + $real_sec}")

    # cleanup
    kubectl delete job "$job_name" --ignore-not-found
  done

  # compute average
  avg=$(awk "BEGIN {printf \"%.3f\", $sum/3}")
  summary="$LOG_DIR/${job_name}_baseline_avg.txt"
  echo "$avg" | tee "$summary"
  echo ">>> $job_name baseline avg = ${avg}s"
done

echo
echo "✅ All baseline runs done, with logs and averages in $LOG_DIR/*.txt"