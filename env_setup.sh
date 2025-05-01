#!/bin/bash

# Set your group number and ETH ID here
GROUP_NUM="94"
ETH_ID="whsieh"
# "ibouchama"

# Set KOPS state store
export KOPS_STATE_STORE="gs://cca-eth-2025-group-${GROUP_NUM}-${ETH_ID}/"

# Set your GCP project
export PROJECT=$(gcloud config get-value project)
