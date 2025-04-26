#!/bin/bash

# Step 1: Create the memcached pod
echo "Creating memcached pod..."
kubectl create -f memcache-t1-cpuset.yaml

# Step 2: Expose the pod with a LoadBalancer service
echo "Exposing memcached service..."
kubectl expose pod some-memcached --name some-memcached-11211 \
  --type LoadBalancer --port 11211 --protocol TCP

# Step 3: Wait for the LoadBalancer IP to be assigned
echo "Waiting 60 seconds for LoadBalancer IP to be assigned..."
sleep 60

# Step 4: Get the service information
echo "Fetching memcached service details:"
kubectl get service some-memcached-11211
