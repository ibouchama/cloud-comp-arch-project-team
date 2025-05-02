import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Baseline run CSV files
baseline2_csv_files_runs = ['results/baseline2_run1.csv', 'results/baseline2_run2.csv', 'results/baseline2_run3.csv']
# CPU run CSV files
cpu_csv_files_runs = ['results/cpu_run1.csv', 'results/cpu_run2.csv', 'results/cpu_run3.csv']
#L1d (Level 1 Data Cache) run CSV files
l1d_csv_files_runs = ['results/l1d_run1.csv', 'results/l1d_run2.csv', 'results/l1d_run3.csv']

#L1i (Level 1 Instruction Cache) run CSV files
l1i_csv_files_runs = ['results/l1i_run1.csv', 'results/l1i_run2.csv', 'results/l1i_run3.csv']
#L2 (Level 2 Cache) run CSV files
l2_csv_files_runs = ['results/l2_run1.csv', 'results/l2_run2.csv', 'results/l2_run3.csv']
#LLC (Last Level Cache = Level 3 Cache) run CSV files
llc_csv_files_runs = ['results/llc_run1.csv', 'results/llc_run2.csv', 'results/llc_run3.csv']
# membw (Memory Bandwidth) run CSV files
membw_csv_files_runs = ['results/membw_run1.csv', 'results/membw_run2.csv', 'results/membw_run3.csv']

# pick one of these to plot:
# runs_to_plot = baseline2_csv_files_runs
# runs_to_plot = cpu_csv_files_runs
# runs_to_plot = l1d_csv_files_runs
# runs_to_plot = l1i_csv_files_runs
# runs_to_plot = l2_csv_files_runs
# runs_to_plot = llc_csv_files_runs
runs_to_plot = membw_csv_files_runs

# label        = 'Baseline2 (3 runs)'
# label        = 'CPU (3 runs)'
# label        = 'L1d (3 runs)'
# label        = 'L1i (3 runs)'
# label        = 'L2 (3 runs)'
# label        = 'LLC (3 runs)'
label        = 'Membw (3 runs)'

# ——— read the header names once from the first file ———
with open(runs_to_plot[0], 'r') as f:
    header = f.readline().lstrip('#').split()

# helper to load a run into a DataFrame with proper column names
def load_run(fp):
    return pd.read_csv(
        fp,
        delim_whitespace=True,
        comment='#',    # skip any other commented lines
        header=None,
        names=header,
        skiprows=1       # drop the header line we just read
    )


# Lists to collect per-run QPS and p95 latency values
qps_runs = []
p95_runs = []

# for run_file in baseline_csv_files_runs:
# for run_file in cpu_csv_files_runs:
for fp in runs_to_plot:
    # Load and parse the metrics file, skipping any comment lines
    df = load_run(fp)
    df = df[df['type'] == 'read']            # keep only the read metrics
    # Column 16 = measured QPS, Column 12 = p95 latency (µs)
    qps = df['QPS'].astype(float).values
    p95 = df['p95'].astype(float).values
    qps_runs.append(qps)
    p95_runs.append(p95)

# Stack into arrays of shape (runs, points)
qps_runs = np.vstack(qps_runs)  # shape: (3, N)
p95_runs = np.vstack(p95_runs)

# Compute mean QPS across runs, and mean/std of p95 latency
qps_mean = np.mean(qps_runs, axis=0)
p95_mean = np.mean(p95_runs, axis=0)
p95_std = np.std(p95_runs, axis=0, ddof=1)

# Convert latencies from µs to ms
p95_mean_ms = p95_mean / 1000.0
p95_std_ms = p95_std / 1000.0

# Plot setup
fig, ax = plt.subplots(figsize=(10, 6))

# ax.errorbar(qps_mean, p95_mean_ms, yerr=p95_std_ms, fmt='-o', capsize=5, label='Baseline (3 runs)')
# ax.errorbar(qps_mean, p95_mean_ms, yerr=p95_std_ms, fmt='-o', capsize=5, label='CPU (3 runs)')
ax.errorbar(qps_mean, p95_mean_ms, yerr=p95_std_ms, fmt='-o', capsize=5, label=label)

ax.set_title(f"{label} Latency vs Queries per Second")

ax.set_xlabel("QPS (queries/sec)")
ax.set_ylabel("Latency (p95) [ms]")
ax.grid(True)
ax.legend()
plt.tight_layout()

# plt.savefig("results_plot/baseline2_latency_vs_qps.png") #experiment1
# plt.savefig("results_plot/cpu_latency_vs_qps.png") #experiment2
# plt.savefig("results_plot/l1d_latency_vs_qps.png") #experiment3
out_png = f"results_plot/{label.lower().replace(' ', '_')}_latency_vs_qps.png"
plt.savefig(out_png)

plt.show()
