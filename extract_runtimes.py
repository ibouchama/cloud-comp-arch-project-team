#!/usr/bin/env python3
import sys
import csv
from datetime import datetime

# List your batch jobs here, in the desired order
JOBS = ["freqmine", "ferret", "canneal", "blackscholes", "vips", "radix", "dedup"]

def parse_runtimes(filename):
    """
    Returns a dict mapping job -> runtime_in_seconds (float) for that run’s log file.
    """
    starts = {}
    ends   = {}
    with open(filename) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            ts_str, event, job = parts[0], parts[1], parts[2]
            if job not in JOBS:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            if event == "start":
                starts[job] = ts
            elif event == "end":
                ends[job] = ts

    durations = {}
    for job in JOBS:
        if job in starts and job in ends:
            durations[job] = (ends[job] - starts[job]).total_seconds()
        else:
            durations[job] = None
    return durations

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} jobs_1.txt [jobs_2.txt ...]")
        sys.exit(1)

    run_files = sys.argv[1:]
    all_runs = [parse_runtimes(f) for f in run_files]

    out_csv = "runtimes.csv"
    with open(out_csv, "w", newline="") as csvf:
        writer = csv.writer(csvf)
        # header: job, run1, run2, ...
        header = ["job"] + [f"run{idx+1}" for idx in range(len(all_runs))]
        writer.writerow(header)

        # per-job rows
        for job in JOBS:
            row = [job]
            for run in all_runs:
                dur = run.get(job)
                row.append(f"{dur:.3f}" if dur is not None else "")
            writer.writerow(row)

        # total row
        total_row = ["total"]
        for run in all_runs:
            total = sum(d for d in run.values() if d is not None)
            total_row.append(f"{total:.3f}")
        writer.writerow(total_row)

    print(f"Wrote per‐job and total runtimes to {out_csv}")

if __name__ == "__main__":
    main()

