#!/usr/bin/env python3
import sys
import pandas as pd
import matplotlib.pyplot as plt

def plot_compute_and_export(csv_path, slope_csv_path, speedup_csv_path):
    # Load the aggregated results
    df = pd.read_csv(csv_path)

    # Identify numeric thread columns (assumes columns named '1','2','4','8', etc.)
    thread_cols = sorted([c for c in df.columns if c.isdigit()], key=int)
    thread_counts = [int(c) for c in thread_cols]

    slopes = []
    speedup_records = []

    plt.figure(figsize=(10, 6))

    for _, row in df.iterrows():
        bench = row['Benchmark']
        # Convert times to float
        times = [float(row[c]) for c in thread_cols]
        base_time = times[0]
        # Compute speedups, rounding to 3 decimal places
        speedups = [1.0] + [round(base_time / t, 3) for t in times[1:]]

        # Record speedups for CSV
        for th, sp in zip(thread_counts, speedups):
            speedup_records.append({
                'Benchmark': bench,
                'Thread': th,
                'Speedup': sp
            })

        # Plot the speedup curve
        plt.plot(thread_counts, speedups, marker='o', label=bench)

        # Compute slopes between consecutive points, rounding to 3 decimals
        for i in range(len(thread_counts) - 1):
            t1, t2 = thread_counts[i], thread_counts[i + 1]
            s1, s2 = speedups[i], speedups[i + 1]
            raw_slope = (s2 - s1) / (t2 - t1)
            slopes.append({
                'Benchmark': bench,
                'Thread_From': t1,
                'Thread_To': t2,
                'Speedup_From': s1,
                'Speedup_To': s2,
                'Slope': round(raw_slope, 3)
            })

    # Finalize plot formatting
    plt.title("Benchmark Speedup vs Number of Threads")
    plt.xlabel("Number of Threads")
    plt.ylabel("Speedup")
    plt.xticks(thread_counts)
    plt.grid(True)
    plt.legend(title="Benchmark", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.show()

    # Write slopes and speedups to CSV files
    pd.DataFrame(slopes).to_csv(slope_csv_path, index=False)
    print(f"Slopes saved to: {slope_csv_path}")
    pd.DataFrame(speedup_records).to_csv(speedup_csv_path, index=False)
    print(f"Speedups saved to: {speedup_csv_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python script.py <input_csv> <slope_csv> <speedup_csv>")
        sys.exit(1)
    input_csv, slope_csv, speedup_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    plot_compute_and_export(input_csv, slope_csv, speedup_csv)

