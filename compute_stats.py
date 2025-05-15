#!/usr/bin/env python3
import csv
import statistics

INPUT_CSV = "runtimes.csv"

def main():
    # Read the CSV into a dict: job -> [run1, run2, ...]
    runtimes = {}
    with open(INPUT_CSV) as f:
        reader = csv.reader(f)
        header = next(reader)              # e.g. ["job","run1","run2","run3"]
        runs = header[1:]
        for row in reader:
            job = row[0]
            # Convert each runtime to float (empty strings -> skip)
            times = [float(x) for x in row[1:] if x != ""]
            runtimes[job] = times

    # Compute and print mean & stdev
    print(f"{'Job':<15} {'Mean (s)':>10} {'StdDev (s)':>12}")
    print("-" * 40)
    for job, times in runtimes.items():
        if len(times) >= 2:
            m = statistics.mean(times)
            sd = statistics.stdev(times)
            print(f"{job:<15} {m:10.3f} {sd:12.3f}")
        elif len(times) == 1:
            print(f"{job:<15} {times[0]:10.3f} {'   N/A':>12}")
        else:
            print(f"{job:<15} {'   N/A':>10} {'   N/A':>12}")

if __name__ == "__main__":
    main()
