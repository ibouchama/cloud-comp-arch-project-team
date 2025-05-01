#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# run_part2a_interference_3x.sh
#
# Spins up CPU interference (iBench) on the 'parsec' node,
# then for each PARSEC Part2a job it:
#   • runs the job 3× under interference
#   • waits for completion
#   • collects logs into results2a_interference/<job>_run<N>.log
#   • cleans up before next run
#
# Usage:
#   chmod +x run_part2a_interference_3x.sh
#   ./run_part2a_interference_3x.sh
#
# Prerequisites:
#   • kubectl context set to part2a.k8s.local
#   • interference/ibench-cpu.yaml uses nodeSelector: parsec
#   • parsec-benchmarks/part2a/*.yaml present
# ==============================================================================

LOG_DIR="results2a_interference_3x"
mkdir -p "$LOG_DIR"

INTERFERE_YAML="interference/ibench-cpu.yaml"
JOB_DIR="parsec-benchmarks/part2a"

echo "Using kubectl context: $(kubectl config current-context)"

for job_file in "$JOB_DIR"/*.yaml; do
  job_name=$(basename "$job_file" .yaml)

  for run in 1 2 3; do
    echo
    echo "=== $job_name: interference run #$run ==="

    # A) Clean up any old Job & interference Pod
    kubectl delete job "$job_name"           --ignore-not-found
    kubectl delete pod ibench-cpu            --ignore-not-found

    # B) Launch interference
    echo -n "Starting CPU interference… "
    kubectl create -f "$INTERFERE_YAML"
    until kubectl get pod ibench-cpu -o jsonpath='{.status.phase}' 2>/dev/null | grep -qx Running; do
      sleep 1
    done
    echo "interference is Running"

    # C) Launch the PARSEC job
    echo "Launching PARSEC job: $job_name (run #$run)"
    kubectl create -f "$job_file"

    # D) Wait for job to complete
    echo -n "Waiting for job/$job_name to complete… "
    kubectl wait --for=condition=complete job/"$job_name" --timeout=600s
    echo "done"

    # E) Collect logs
    pod=$(kubectl get pods --selector=job-name="$job_name" --output=jsonpath='{.items[*].metadata.name}')
    out="$LOG_DIR/${job_name}_run${run}.log"
    echo "Collecting logs → $out"
    kubectl logs "$pod" > "$out"

    # F) Tear down this run
    kubectl delete job "$job_name"           --ignore-not-found
    kubectl delete pod ibench-cpu            --ignore-not-found

    echo "=== Finished $job_name run #$run ==="
  done
done

echo
echo "✅ All interference runs (3× each) complete. Logs in $LOG_DIR/" 
