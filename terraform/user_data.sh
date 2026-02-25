#!/bin/bash
set -euxo pipefail

# Update system (Amazon Linux 2023 uses dnf)
dnf update -y

# Install Docker
dnf install docker -y
systemctl start docker
systemctl enable docker

# Install Docker Compose v2
DOCKER_COMPOSE_VERSION="v2.32.4"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Install Git
dnf install -y git

# Install cronie for scheduled tasks
dnf install -y cronie
systemctl enable crond
systemctl start crond

# Install rsync for deployments
dnf install -y rsync

# Add ec2-user to docker group
usermod -aG docker ec2-user

# Create app directory
mkdir -p /opt/procurement-intel
chown ec2-user:ec2-user /opt/procurement-intel

# Create directories for scripts and logs
mkdir -p /opt/procurement-intel/scripts
mkdir -p /opt/procurement-intel/logs
chown -R ec2-user:ec2-user /opt/procurement-intel

echo "User data setup complete" > /var/log/user-data-complete.log
