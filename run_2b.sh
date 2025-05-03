#!/usr/bin/env bash

set -euo pipefail

echo " ============= Running 1 Thread Script ============ "
./run_baseline2b_1T.sh

echo " ============= Running 2 Threads Script ============ "
./run_baseline2b_2T.sh

echo " ============= Running 4 Threads Script ============ "
./run_baseline2b_4T.sh


echo " ============= Running 8 Threads Script ============ "
./run_baseline2b_8T.sh


echo " All Scripts Ran Completely "
