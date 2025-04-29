#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# run_part2a_interference_3x_avg.sh
#
# Like run_part2a_interference_3x.sh, but also computes the average of the 3
# 'real' times (in seconds) for each job under CPU interference.
#
# Outputs:
#   • 3 raw logfiles: results2a_interference_3x/<job>_run<N>.log
#   • 1 summary per job:    results2a_interference_3x_avg/<job>_avg.txt
#   • Prints each job’s average to stdout
# ==============================================================================

LOG_DIR="results2a_interference_3x"
# LOG_DIR="results2a_interference_3x_avg"
mkdir -p "$LOG_DIR"

INTERFERE_YAML="interference/ibench-cpu.yaml"
JOB_DIR="parsec-benchmarks/part2a"

echo "Using kubectl context: $(kubectl config current-context)"

for job_file in "$JOB_DIR"/*.yaml; do
  job_name=$(basename "$job_file" .yaml)
  sum=0

  for run in 1 2 3; do
    echo
    echo "=== $job_name: interference run #$run ==="

    # teardown from any prior run
    kubectl delete job "$job_name" --ignore-not-found
    kubectl delete pod ibench-cpu  --ignore-not-found

    # start interference
    kubectl create -f "$INTERFERE_YAML"
    until kubectl get pod ibench-cpu -o jsonpath='{.status.phase}' 2>/dev/null | grep -qx Running; do
      sleep 1
    done

    # launch the job
    kubectl create -f "$job_file"
    kubectl wait --for=condition=complete job/"$job_name" --timeout=600s

    # grab the single Pod name
    pod=$(kubectl get pods -l job-name="$job_name" \
          -o jsonpath='{.items[0].metadata.name}')
    out="$LOG_DIR/${job_name}_run${run}.log"
    kubectl logs "$pod" > "$out"

    # parse the 'real' time, converting 0mSS.SSSs to seconds
    real_line=$(grep '^real' "$out")
    # extract minutes and seconds
    read min sec <<< $(echo "$real_line" | sed -E 's/real\s+([0-9]+)m([0-9.]+)s/\1 \2/')
    real_sec=$(awk "BEGIN {printf \"%.3f\", $min*60 + $sec}")

    echo "  run #$run real_time = ${real_sec}s"
    sum=$(awk "BEGIN {printf \"%.3f\", $sum + $real_sec}")

    # cleanup this run
    kubectl delete job "$job_name" --ignore-not-found
    kubectl delete pod ibench-cpu  --ignore-not-found
  done

  # compute the average
  avg=$(awk "BEGIN {printf \"%.3f\", $sum/3}")
  summary="$LOG_DIR/${job_name}_avg.txt"
  echo "$avg" | tee "$summary"
  echo ">>> $job_name average real_time_under_cpu = ${avg}s"
done

echo
echo "✅ All runs done, with averages in $LOG_DIR/*.txt"

