#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# run_part2a_all_interference_3x_avg.sh
#
# For each interference type (cpu l1d l1i l2 llc membw) and for each PARSEC Part2a job:
#   • runs the job 3× under that interference
#   • waits for completion
#   • collects per‐run logs in results2a_interferences_3x/results2a_<type>_3x/
#   • computes the average 'real' time and writes results2a_interferences_3x/results2a_<type>_3x_avg/<job>_avg.txt
#
# Usage:
#   chmod +x run_part2a_all_interference_3x_avg.sh
#   ./run_part2a_all_interference_3x_avg.sh
#
# Prereqs:
#   • kubectl context = part2a.k8s.local
#   • interference/ibench-<type>.yaml present for cpu, l1d, l1i, l2, llc, and membw.
#   • parsec-benchmarks/part2a/*.yaml present
# ==============================================================================

# List all interference modes you want to test
INTER_TYPES=(cpu l1d l1i l2 llc membw)

# Folder with PARSEC job specs
JOB_DIR="parsec-benchmarks/part2a"

echo "Using kubectl context: $(kubectl config current-context)"
echo

for type in "${INTER_TYPES[@]}"; do
  echo "=== Starting interference type: $type ==="
  INTERFER_YAML="interference/ibench-${type}.yaml"

  # Directories for raw logs and averages
  RAW_DIR="results2a_interferences_3x/results2a_${type}_3x"
  AVG_DIR="results2a_interferences_3x/results2a_${type}_3x_avg"
  mkdir -p "$RAW_DIR" "$AVG_DIR"

  for job_file in "$JOB_DIR"/*.yaml; do
    job_name=$(basename "$job_file" .yaml)
    sum=0

    echo
    echo "---> $job_name under '$type' interference (3 runs)"

    for run in 1 2 3; do
      echo "  • Run #$run"

      # Clean up prior job & interference pod
      kubectl delete job "$job_name"        --ignore-not-found
      kubectl delete pod ibench-"$type"     --ignore-not-found

      # Launch interference
      kubectl create -f "$INTERFER_YAML"
      # Wait until the interference Pod is Running
      until kubectl get pod ibench-"$type" \
              -o jsonpath='{.status.phase}' 2>/dev/null \
              | grep -qx Running; do
        sleep 1
      done

      # Launch the PARSEC job
      kubectl create -f "$job_file"
      kubectl wait --for=condition=complete job/"$job_name" --timeout=600s

      # Grab its Pod name
      pod=$(kubectl get pods -l job-name="$job_name" -o jsonpath='{.items[0].metadata.name}')

      # Save logs
      raw_log="$RAW_DIR/${job_name}_run${run}.log"
      kubectl logs "$pod" > "$raw_log"

      # Parse the “real XmY.ZZs” line
      real_line=$(grep '^real' "$raw_log")
      read -r min sec <<<"$(
        echo "$real_line" | sed -E 's/real\s+([0-9]+)m([0-9.]+)s/\1 \2/'
      )"
      # Convert to seconds
      real_sec=$(awk -v m="$min" -v s="$sec" \
                    'BEGIN {printf "%.3f", m*60 + s}')
      echo "    real_time = ${real_sec}s"
      # Accumulate
      sum=$(awk -v total="$sum" -v r="$real_sec" \
                  'BEGIN {printf "%.3f", total + r}')

      # Tear down this run
      kubectl delete job "$job_name"        --ignore-not-found
      kubectl delete pod ibench-"$type"     --ignore-not-found
    done

    # Compute & write average
    avg=$(awk -v total="$sum" 'BEGIN {printf "%.3f", total/3}')
    echo "$avg" | tee "$AVG_DIR/${job_name}_avg.txt"
    echo "  ==> $job_name average under $type = ${avg}s"

  done

  echo
  echo "=== Completed all jobs under '$type'."
  echo "Raw logs in:    $RAW_DIR/"
  echo "Averages in:    $AVG_DIR/"
  echo
done

echo "✅ All interference experiments (cpu l1d l1i l2 llc membw) done."
