#!/bin/bash
# First-boot setup for the FinOps Tool server (Ubuntu 24.04). Installs Docker
# only; the app itself is deployed by an operator — see docs/DEPLOY_DEBIAN.md.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker

mkdir -p /opt/finops
