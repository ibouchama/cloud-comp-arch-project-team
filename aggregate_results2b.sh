#!/usr/bin/env bash
set -euo pipefail

# ===============================================================================
# aggregate_avg_to_csv.sh
#
# Scans all result folders (1threads, 2threads, 4threads, 8threads) for *_baseline_avg.txt
# files, extracts the benchmark names and averages, and writes a CSV table:
#
# Benchmark,1,2,4,8
# blackscholes,86.478,85.956,83.451,81.983
# canneal, ...
# ===============================================================================

RESULTS_ROOT="results2b_baseline_3x_avg"
THREAD_COUNTS=(1 2 4 8)
OUTPUT_CSV="aggregated_results.csv"

declare -A data

echo "Scanning for average files..."

# Collect all benchmark names
benchmarks=()
for thread in "${THREAD_COUNTS[@]}"; do
  DIR="$RESULTS_ROOT/${thread}threads"
  for file in "$DIR"/*_baseline_avg.txt; do
    filename=$(basename "$file")
    bench_name=$(echo "$filename" | sed -E 's/_t[0-9]+_baseline_avg\.txt//')
    [[ " ${benchmarks[*]} " == *" $bench_name "* ]] || benchmarks+=("$bench_name")
    avg=$(cat "$file")
    data["$bench_name,$thread"]="$avg"
  done
done

# Write CSV header
{
  printf "Benchmark"
  for thread in "${THREAD_COUNTS[@]}"; do
    printf ",%s" "$thread"
  done
  printf "\n"

  # Write rows
  for bench in "${benchmarks[@]}"; do
    printf "%s" "$bench"
    for thread in "${THREAD_COUNTS[@]}"; do
      val="${data["$bench,$thread"]:-}"
      printf ",%s" "$val"
    done
    printf "\n"
  done
} > "$OUTPUT_CSV"


echo "✅ Aggregated results saved to $OUTPUT_CSV"

