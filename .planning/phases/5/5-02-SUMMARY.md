---
phase: 5-scheduling-and-hardening
plan: 02
subsystem: scheduling
tags: [cron, flock, docker-prune, retention, scripts]
dependency_graph:
  requires: [docker-compose.yml, docker-compose.prod.yml, scraper/main.py]
  provides: [nightly-scrape-automation, listing-retention-cleanup, docker-disk-management, crontab-installer]
  affects: [scraper-scheduling, database-maintenance, disk-usage]
tech_stack:
  added: []
  patterns: [flock-overlap-protection, cron-tz-aware-scheduling, docker-system-prune]
key_files:
  created:
    - scripts/nightly-scrape.sh
    - scripts/docker-prune.sh
    - scripts/install-crontab.sh
  modified: []
decisions:
  - "flock -n non-blocking lock: skip run if previous still active (no queue, no wait)"
  - "CRON_TZ=America/Toronto over ET for DST-aware IANA timezone handling"
  - "Retention cleanup runs unconditionally after scrape (even if scrape fails)"
  - "docker system prune --filter until=168h protects recently-built images"
  - "install-crontab.sh replaces full crontab (idempotent)"
metrics:
  duration: ~1min
  completed: 2026-02-24
---

# Phase 5 Plan 02: Scheduling Scripts Summary

Nightly scrape script with flock overlap protection and 1-year listing retention cleanup, weekly Docker prune, and CRON_TZ-aware crontab installer for EC2 deployment.

## What Was Done

### Task 1: Nightly Scrape Script

Created `scripts/nightly-scrape.sh` -- the primary automation script triggered by cron at 2 AM ET:

- **flock -n** for non-blocking overlap protection: if a previous scrape is still running, the new invocation exits immediately with a warning rather than queueing or waiting
- **docker compose exec -T** with prod overlay (`-f docker-compose.yml -f docker-compose.prod.yml`): the `-T` flag prevents TTY allocation errors when running under cron
- **xvfb-run** wraps the Python scraper command to provide a virtual display for Chromium-based browser automation (DISPLAY is per-process-tree, not inherited from container PID 1)
- **Listing retention cleanup** runs unconditionally after the scrape: `DELETE FROM listings WHERE closing_date < NOW() - INTERVAL '1 year'`. NULL closing_dates are safe (NULL comparison yields NULL, not TRUE)
- All output (stdout + stderr) appended to `/opt/procurement-intel/logs/nightly-scrape.log` with timestamps

### Task 2: Docker Prune Script and Crontab Installer

Created `scripts/docker-prune.sh` -- weekly cleanup of Docker artifacts:
- `docker system prune -f --filter "until=168h"` removes images, stopped containers, and unused networks older than 7 days
- `-f` flag skips interactive confirmation prompt
- Logged with timestamps to `/opt/procurement-intel/logs/docker-prune.log`

Created `scripts/install-crontab.sh` -- one-time crontab setup for EC2:
- Sets `CRON_TZ=America/Toronto` (IANA timezone, handles DST correctly)
- Schedules nightly scrape at `0 2 * * *` (2 AM ET)
- Schedules weekly Docker prune at `0 4 * * 0` (4 AM ET Sundays)
- Validates both scripts exist before installing crontab
- Idempotent: replaces entire crontab on each run
- Requires cronie installed and crond running (documented in script header)

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 8873f54 | Nightly scrape script with flock overlap protection |
| 2 | 82a8940 | Docker prune script and crontab installer |

## Key Files

| File | Action | Purpose |
|------|--------|---------|
| scripts/nightly-scrape.sh | Created | Nightly scrape with flock, xvfb, retention cleanup |
| scripts/docker-prune.sh | Created | Weekly Docker artifact cleanup |
| scripts/install-crontab.sh | Created | EC2 crontab installation helper |

## Self-Check: PASSED

- scripts/nightly-scrape.sh: FOUND
- scripts/docker-prune.sh: FOUND
- scripts/install-crontab.sh: FOUND
- 5-02-SUMMARY.md: FOUND
- Commit 8873f54: FOUND
- Commit 82a8940: FOUND
