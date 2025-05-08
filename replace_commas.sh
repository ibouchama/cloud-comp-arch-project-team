#!/usr/bin/env bash
set -euo pipefail

# ===============================================================================
# replace_commas_with_dots.sh
#
# Scans thread result folders (1threads, 2threads, 4threads, 8threads) for
# *_baseline_avg.txt files and replaces commas with dots in-place.
#
# Usage:
#   chmod +x replace_commas_with_dots.sh
#   ./replace_commas_with_dots.sh [results_root]
#
# If results_root is not provided, defaults to current directory.
# ===============================================================================

# Root directory containing the thread folders (default: current)
ROOT_DIR="results2b_baseline_3x_avg"
THREAD_COUNTS=(1 2 4 8)

# Choose sed in-place options based on OS
case "$(uname)" in
  Darwin*) SED_OPTS=(-i '');;
  *)       SED_OPTS=(-i);;
esac

for threads in "${THREAD_COUNTS[@]}"; do
  DIR="$ROOT_DIR/${threads}threads"
  if [[ ! -d "$DIR" ]]; then
    echo "Warning: directory $DIR not found, skipping." >&2
    continue
  fi

  for file in "$DIR"/*_baseline_avg.txt; do
    [[ -f "$file" ]] || continue
    echo "Processing $file"
    # Replace all commas with dots in-place
    sed "${SED_OPTS[@]}" 's/,/./g' "$file"
  done
done

echo "✅ All files processed."

