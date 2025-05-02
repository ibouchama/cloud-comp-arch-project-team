import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Label-to-paths mapping for all run files
run_files = {
    "none": [
        "results/none_run1.csv",
        "results/none_run2.csv",
        "results/none_run3.csv",
    ],
    "cpu": [
        "results/cpu_run1.csv",
        "results/cpu_run2.csv",
        "results/cpu_run3.csv",
    ],
    "l1d": [
        "results/l1d_run1.csv",
        "results/l1d_run2.csv",
        "results/l1d_run3.csv",
    ],
    "l1i": [
        "results/l1i_run1.csv",
        "results/l1i_run2.csv",
        "results/l1i_run3.csv",
    ],
    "l2": [
        "results/l2_run1.csv",
        "results/l2_run2.csv",
        "results/l2_run3.csv",
    ],
    "llc": [
        "results/llc_run1.csv",
        "results/llc_run2.csv",
        "results/llc_run3.csv",
    ],
    "membw": [
        "results/membw_run1.csv",
        "results/membw_run2.csv",
        "results/membw_run3.csv",
    ],
}

# ——— read the header names once from the first file ———
with open(run_files["none"][0], 'r') as f:
    header = f.readline().lstrip('#').split()

# Helper to load one run
def load_run(fp):
    return pd.read_csv(
        fp,
        delim_whitespace=True,
        comment='#',
        header=None,
        names=header,
        skiprows=1
    )

# Process each interference type
aggregated_data = {}
for label, file_list in run_files.items():
    qps_runs = []
    p95_runs = []

    for fp in file_list:
        df = load_run(fp)
        df = df[df["type"] == "read"]
        qps = df["QPS"].astype(float).values
        p95 = df["p95"].astype(float).values
        qps_runs.append(qps)
        p95_runs.append(p95)

    qps_array = np.vstack(qps_runs)
    p95_array = np.vstack(p95_runs)

    qps_mean = np.mean(qps_array, axis=0)
    p95_mean = np.mean(p95_array, axis=0)
    p95_std = np.std(p95_array, axis=0, ddof=1)

    aggregated_data[label] = {
        "qps": qps_mean,
        "latency_mean_ms": p95_mean / 1000.0,
        "latency_std_ms": p95_std / 1000.0,
    }

# ——— Plotting all in one chart ———
plt.figure(figsize=(12, 8))

for label, data in aggregated_data.items():
    plt.errorbar(
        data["qps"],
        data["latency_mean_ms"],
        yerr=data["latency_std_ms"],
        fmt="-o",
        capsize=3,
        label=label
    )

plt.title("95th Percentile Latency vs QPS with Different Interference Types\n(3 repetitions per point)")
plt.xlabel("Queries per Second (QPS)")
plt.ylabel("95th Percentile Latency (ms)")
plt.legend(title="Interference Type")
plt.grid(True)
plt.tight_layout()
plt.savefig("results_plot/all_interference_latency_vs_qps.png")
plt.show()

# python3 multi-line_plot_part1.py