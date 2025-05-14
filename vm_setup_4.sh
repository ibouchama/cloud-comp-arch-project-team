#!/usr/bin/env bash
set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────────────────────
ZONE="europe-west1-b"
SSH_USER="ubuntu"

# Your Part-4 instance names
CLIENT_AGENT="client-agent-21ww"
CLIENT_MEASURE="client-measure-ks71"

# ─── Script to set up a single VM ──────────────────────────────────────────────
setup_vm() {
  local instance="$1"
  echo "🚀 Setting up VM: $instance"

  gcloud compute ssh "${SSH_USER}@${instance}" \
    --zone "${ZONE}" \
    --ssh-key-file ~/.ssh/cloud-computing \
    --command '
      set -euo pipefail
      echo "🔧 Updating package lists and enabling source repos..."
      sudo sed -i "s/^Types: deb$/Types: deb deb-src/" /etc/apt/sources.list.d/ubuntu.sources
      sudo apt-get update
      echo "📦 Installing required packages..."
      sudo apt-get install -y libevent-dev libzmq3-dev git make g++
      echo "📦 Installing memcached build dependencies..."
      sudo apt-get build-dep -y memcached
      echo "📂 Cloning memcache-perf-dynamic repository..."
      if [ ! -d "$HOME/memcache-perf-dynamic" ]; then
        git clone https://github.com/eth-easl/memcache-perf-dynamic.git
      fi
      cd memcache-perf-dynamic
      echo "⚙️ Building mcperf..."
      make
      echo "✅ Setup completed on $(hostname)"
    '
}

# ─── Setup each VM ─────────────────────────────────────────────────────────────
for INSTANCE in "${CLIENT_AGENT}" "${CLIENT_MEASURE}"; do
  setup_vm "${INSTANCE}"
done

echo "🎉 All VMs have been successfully set up!"

