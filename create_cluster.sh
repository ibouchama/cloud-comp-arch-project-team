#!/bin/bash

source env_setup.sh

# Create the cluster
kops create -f part1.yaml

# Add SSH key to the cluster
kops create secret --name part1.k8s.local sshpublickey admin -i ~/.ssh/cloud-computing.pub

# Deploy the cluster
kops update cluster --name part1.k8s.local --yes --admin

# Validate the cluster (optional, but useful)
kops validate cluster --wait 10m
