---
phase: 5-scheduling-and-hardening
plan: 01
subsystem: infrastructure
tags: [docker, production, ec2, provisioning]
dependency_graph:
  requires: [docker-compose.yml, terraform/user_data.sh]
  provides: [docker-compose.prod.yml, updated-ec2-provisioning]
  affects: [deployment, scraper-scheduling]
tech_stack:
  added: []
  patterns: [docker-compose-overlay, image-digest-pinning, json-file-log-rotation]
key_files:
  created:
    - docker-compose.prod.yml
  modified:
    - terraform/user_data.sh
decisions:
  - "restart: always over unless-stopped for reboot recovery"
  - "Scraper sleep infinity for cron-based docker compose exec invocations"
  - "50MB max log per service (10m x 5 files)"
  - "Real sha256 digests fetched from registry for pgvector and nginx"
metrics:
  duration: ~1min
  completed: 2026-02-24
---

# Phase 5 Plan 01: Production Docker Compose Overlay and EC2 Provisioning Summary

Production Docker Compose overlay with restart:always, log rotation, digest-pinned images, and scraper sleep-infinity; EC2 user_data.sh updated with cronie, rsync, and directory structure.

## What Was Done

### Task 1: Production Docker Compose Overlay
Created `docker-compose.prod.yml` as a merge overlay for the base `docker-compose.yml`. The overlay applies production hardening without modifying the development configuration:

- **restart: always** on all 5 services (db, scraper, api, web, nginx) -- ensures recovery after EC2 reboots, unlike `unless-stopped` which won't restart after `docker stop`
- **JSON-file log rotation** on all 5 services: 10MB per file, 5 files max = 50MB per service, 250MB total worst case
- **Image digest pinning** for registry-pulled images:
  - `pgvector/pgvector:pg17@sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21`
  - `nginx:alpine@sha256:1d13701a5f9f3fb01aaa88cef2344d65b6b5bf6b7d9fa4cf0dca557a8d7702ba`
- **Scraper command override**: `["sleep", "infinity"]` keeps the container alive for `docker compose exec` cron invocations. The Dockerfile CMD (main.py) remains unchanged for dev use.

Validated with `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet`.

### Task 2: EC2 user_data.sh Update
Updated `terraform/user_data.sh` with additional provisioning for scheduled tasks:

- **cronie**: Installed and enabled for crontab-based scheduling (nightly scraper, certbot renewal)
- **rsync**: Installed for deployment file transfers (not in AL2023 by default)
- **Directory structure**: Created `/opt/procurement-intel/scripts` and `/opt/procurement-intel/logs` with recursive ec2-user ownership

All existing provisioning steps preserved intact.

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 6e6ca4b | Production Docker Compose overlay with hardened config |
| 2 | 3440537 | EC2 provisioning with cronie and directory setup |

## Key Files

| File | Action | Purpose |
|------|--------|---------|
| docker-compose.prod.yml | Created | Production overlay with restart, logging, digests |
| terraform/user_data.sh | Modified | Added cronie, rsync, scripts/logs directories |

## Self-Check: PASSED

- docker-compose.prod.yml: FOUND
- terraform/user_data.sh: FOUND
- 5-01-SUMMARY.md: FOUND
- Commit 6e6ca4b: FOUND
- Commit 3440537: FOUND
