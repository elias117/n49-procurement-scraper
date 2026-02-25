#!/bin/bash
# Weekly Docker cleanup — removes old images, stopped containers, unused networks
# Runs Sundays at 4 AM ET via cron

LOGFILE=/opt/procurement-intel/logs/docker-prune.log

exec >> "$LOGFILE" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Docker prune starting ==="

# Prune artifacts older than 7 days; -f skips confirmation prompt
docker system prune -f --filter "until=168h"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Docker prune complete ==="
