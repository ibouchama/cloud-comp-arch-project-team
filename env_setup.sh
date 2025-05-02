#!/bin/bash

# Set your group number and ETH ID here
GROUP_NUM="94"    # e.g., 001
ETH_ID="sbouabid"  # e.g., rbonouag

# Set KOPS state store
export KOPS_STATE_STORE="gs://cca-eth-2025-group-${GROUP_NUM}-${ETH_ID}/"

# Set your GCP project
export PROJECT=$(gcloud config get-value project)
