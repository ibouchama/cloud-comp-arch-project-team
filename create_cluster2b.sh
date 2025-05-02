#!/bin/bash

# Execute each line in the env_setup.sh script
source env_setup.sh

# Create the cluster
kops create -f part2b.yaml

# Add SSH key to the cluster
kops create secret --name part2b.k8s.local sshpublickey admin -i ~/.ssh/cloud-computing.pub

# Deploy the cluster
kops update cluster --name part2b.k8s.local --yes --admin

# Validate the cluster (optional, but useful)
kops validate cluster --wait 10m
#  --count 3
