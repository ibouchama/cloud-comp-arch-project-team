#!/bin/bash

source env_setup.sh

# Clean old bucket if exists
gsutil rm -r "gs://cca-eth-2025-group-${GROUP_NUM}-${ETH_ID}/" || true

# Create new bucket
gsutil mb "gs://cca-eth-2025-group-${GROUP_NUM}-${ETH_ID}/"
