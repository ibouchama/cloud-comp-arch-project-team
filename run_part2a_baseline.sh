#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="results2a_baseline"
mkdir -p "$LOG_DIR"
JOB_DIR="parsec-benchmarks/part2a"

for yaml in "$JOB_DIR"/*.yaml; do
  name=$(basename "$yaml" .yaml)
  echo "=== Baseline run for $name ==="

  # Clean up any old job
  kubectl delete job "$name" --ignore-not-found

  # Launch only the PARSEC job
  kubectl create -f "$yaml"

  # Wait for completion
  kubectl wait --for=condition=complete job/"$name" --timeout=600s

  # Fetch real time from logs
  pod=$(kubectl get pods --selector=job-name="$name" --output=jsonpath='{.items[*].metadata.name}')
#   pod=$(kubectl get pods -l job-name="$name" \
#         -o jsonpath='{.items[*].metadata.name}')
  echo "  Logs → $LOG_DIR/$name.log"
  kubectl logs "$pod" > "$LOG_DIR/$name.log"

  # Tear down
  kubectl delete job "$name"
done

echo "Baseline runs complete; see $LOG_DIR/"

# chmod +x run_part2a_baseline.sh
# ./run_part2a_baseline.sh

#look at the output real 's value