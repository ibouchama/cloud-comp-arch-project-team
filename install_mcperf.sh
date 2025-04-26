#!/bin/bash

# This script installs and builds mcperf on a VM
echo "Updating packages..."
sudo apt-get update

echo "Installing required dependencies..."
sudo apt-get install libevent-dev libzmq3-dev git make g++ --yes

echo "Fixing sources.list to allow build-dep..."
sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources
sudo apt-get update

echo "Installing memcached build dependencies..."
sudo apt-get build-dep memcached --yes

echo "Cloning mcperf repository..."
cd ~
git clone https://github.com/shaygalon/memcache-perf.git
cd memcache-perf

echo "Checking out specific commit..."
git checkout 0afbe9b

echo "Building mcperf..."
make

echo "✅ mcperf installation complete!"
