#!/bin/bash
# Nightly procurement scraper — triggered by cron at 2 AM ET
# Uses flock to prevent overlapping runs

LOCKFILE=/tmp/procurement-scrape.lock
LOGFILE=/opt/procurement-intel/logs/nightly-scrape.log
PROJECT_DIR=/opt/procurement-intel

# Append all output to log file
exec >> "$LOGFILE" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Nightly scrape starting ==="

cd "$PROJECT_DIR" || exit 1

# Ensure docker compose uses prod overlay
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# Run scraper with flock (non-blocking: skip if previous run still going)
# -T: no TTY (required for cron — no terminal available)
# xvfb-run: provides virtual display for Chromium (DISPLAY is per-process-tree)
flock -n "$LOCKFILE" \
  $COMPOSE exec -T scraper \
    xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python scraper/main.py

SCRAPE_EXIT=$?

if [ $SCRAPE_EXIT -eq 1 ]; then
  echo "WARN: flock could not acquire lock — previous run still active, skipping"
elif [ $SCRAPE_EXIT -ne 0 ]; then
  echo "ERROR: scraper exited with code $SCRAPE_EXIT"
else
  echo "Scraper completed successfully"
fi

# Retention cleanup: delete listings with closing_date > 1 year old
# NULL closing_dates are NOT deleted (NULL < threshold = NULL, not TRUE)
echo "Running listing retention cleanup..."
$COMPOSE exec -T db psql -U procurement -d procurement -c \
  "DELETE FROM listings WHERE closing_date < NOW() - INTERVAL '1 year';"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Nightly scrape complete ==="
