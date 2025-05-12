"""
compute the mean and population standard deviation of three time measurements given in HH:MM:SS format.
"""

import sys


def to_seconds(timestr):
    """Convert HH:MM:SS string to total seconds (int)."""
    h, m, s = map(int, timestr.split(':'))
    return h * 3600 + m * 60 + s


def format_seconds(seconds):
    """Format a float number of seconds with two decimal places."""
    return f"{seconds:.2f} s"


if len(sys.argv) != 4:
    print(f"Usage: {sys.argv[0]} time1 time2 time3")
    print("Each time should be in HH:MM:SS format, e.g., 00:01:28")
    sys.exit(1)

# Parse input times
times_in = sys.argv[1:]
times_sec = [to_seconds(t) for t in times_in]

# Compute statistics (population std)
mean_sec = sum(times_sec) / len(times_sec)
var_pop = sum((t - mean_sec) ** 2 for t in times_sec) / len(times_sec)
std_pop = var_pop ** 0.5

# Output results
print("Inputs (s):", times_sec)
print("Mean:", format_seconds(mean_sec))
print("Population Std Dev:", format_seconds(std_pop))
