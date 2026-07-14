#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 docker-buildx git
systemctl enable --now docker

rm -rf /home/azureuser/azure_support_engineer_p1
git clone https://github.com/Asere231/azure_support_engineer_p1.git /home/azureuser/azure_support_engineer_p1

cd /home/azureuser/azure_support_engineer_p1/fast_api

docker compose up -d --build

docker compose ps
sleep 5
curl -I http://localhost:8081/health || curl -I http://localhost:8081/

#Fix folder permissions
chown -R azureuser:azureuser /home/azureuser/azure_support_engineer_p1