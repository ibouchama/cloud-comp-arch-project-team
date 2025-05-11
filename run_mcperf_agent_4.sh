#!/usr/bin/env bash
set -euo pipefail

# Path to the mcperf binary
MCPERF_BIN="$HOME/memcache-perf-dynamic/mcperf"

# Check that it exists
if [[ ! -x "$MCPERF_BIN" ]]; then
  echo "ERROR: mcperf not found or not executable at $MCPERF_BIN"
  exit 1
fi

# Output log file
LOGFILE="$HOME/mcperf-agent.log"

echo "Starting mcperf agent with 8 threads..."
nohup "$MCPERF_BIN" -T 8 -A > "$LOGFILE" 2>&1 &

PID=$!
echo "Launched mcperf (PID $PID); logging to $LOGFILE"

#todo: chatgpt says no need to write, but spin it is enough? Pass all the part4 description to it until ./mcperf -t 8 -A