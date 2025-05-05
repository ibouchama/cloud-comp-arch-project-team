#!/usr/bin/env bash
set -euo pipefail

echo "→ Enabling source repos in ubuntu.sources…"
sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources

echo "→ Updating apt cache…"
sudo apt-get update

echo "→ Installing core build tools and libraries…"
sudo apt-get install -y libevent-dev libzmq3-dev git make g++

echo "→ Installing memcached build-dependencies…"
sudo apt-get build-dep -y memcached

echo "→ Cloning (or updating) the augmented mcperf repo…"
if [ -d "$HOME/memcache-perf-dynamic" ]; then
  echo "   • ~/memcache-perf-dynamic already exists, pulling latest changes"
  cd "$HOME/memcache-perf-dynamic"
  git pull
else
  git clone https://github.com/eth-easl/memcache-perf-dynamic.git "$HOME/memcache-perf-dynamic"
  cd "$HOME/memcache-perf-dynamic"
fi

echo "→ Building mcperf…"
make

echo "✅ install_mcperf_3.sh: all done!"
