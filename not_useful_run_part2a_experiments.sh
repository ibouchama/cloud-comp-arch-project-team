#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# run_part2a_workloads.sh
#
# Spins up CPU interference (iBench) on the 'parsec' node,
# then runs each PARSEC Part2a job one at a time, waits for completion,
# collects logs, and cleans up before the next iteration.
#
# Usage:
#   chmod +x run_part2a_workloads.sh
#   ./run_part2a_workloads.sh
#
# Prerequisites:
#   • kubectl context set to part2a.k8s.local
#   • INTERFERE_YAML updated to label parsec nodeSelector
#   • parsec-benchmarks/part2a/*.yaml in place
# ==============================================================================

# Where to dump logs
LOG_DIR="results2a_interference"
mkdir -p "$LOG_DIR"

# Path to your interference YAML (must use parsec nodeSelector) :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}
INTERFERE_YAML="interference/ibench-cpu.yaml"

# Directory containing your Part2a job templates :contentReference[oaicite:2]{index=2}&#8203;:contentReference[oaicite:3]{index=3}
JOB_DIR="parsec-benchmarks/part2a"

# Verify kubectl context
echo "Using kubectl context: $(kubectl config current-context)"

for job_file in "$JOB_DIR"/*.yaml; do
  job_name=$(basename "$job_file" .yaml)
  echo
  echo "=== Running interference + $job_name ==="

  # 1) Clean up any old interference pod
  echo "Cleaning up old interference pod..."
  kubectl delete job "$job_name" --ignore-not-found
  kubectl delete pod ibench-cpu --ignore-not-found

  # 2) Launch interference
  echo "Launching interference..."
  kubectl create -f "$INTERFERE_YAML"

  # 3) Wait for ibench-cpu to enter Running phase
  echo -n "Waiting for ibench-cpu to be Running..."
  until kubectl get pod ibench-cpu -o jsonpath='{.status.phase}' 2>/dev/null | grep -q "^Running$"; do
    echo -n "."
    sleep 2
  done
  echo " ✓ interference is Running!"

  # 4) Launch the PARSEC batch job
  echo "Launching PARSEC job: $job_name"
  kubectl create -f "$job_file"

  # 5) Wait for job completion
  echo -n "Waiting for job/$job_name to complete..."
  kubectl wait --for=condition=complete job/"$job_name" --timeout=600s
  echo " done."

  # 6) Collect logs
  pod=$(kubectl get pods --selector=job-name="$job_name" --output=jsonpath='{.items[*].metadata.name}')
  echo "Gathering logs from pod $pod → $LOG_DIR/${job_name}.log"
  kubectl logs "$pod" > "$LOG_DIR/${job_name}.log"

  # 7) Clean up job and interference
  echo "Deleting job and interference pod..."
  kubectl delete job "$job_name"           --ignore-not-found
  kubectl delete pod ibench-cpu            --ignore-not-found

  echo "=== Finished $job_name ==="
done

echo
echo "✅ All Part2a workloads complete. Logs are in $LOG_DIR/"

# chmod +x run_part2a_workloads.sh
# ./run_part2a_workloads.sh
# Note: The above script assumes that the interference YAML file is set up

#look at the output real 's value