#!/bin/bash
# One-time server setup for the EC2 host (Ubuntu 24.04, ARM64).
# Paste this whole file into: EC2 > Launch instance > Advanced details > User data.
# It runs once, as root, on first boot. Progress: `cloud-init status` on the server.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y docker.io docker-compose-v2
usermod -aG docker ubuntu

# Keep container logs from filling the disk.
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
JSON
systemctl enable docker
systemctl restart docker

# 2 GB swap: the server has 1 GB of RAM; swap absorbs image loads and memory spikes.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Where scripts/ec2-deploy.sh puts compose.yaml, Caddyfile and the app's env file.
install -d -o ubuntu -g ubuntu -m 750 /opt/whitespace
