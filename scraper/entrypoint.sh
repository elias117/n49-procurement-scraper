#!/bin/bash
# Start Xvfb and keep the container alive.
# Cron triggers scraper runs via: docker exec procurement-intel-scraper-1 python scraper/main.py

Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=:99

echo "Xvfb started on :99 — container ready for scraper runs."

# Keep container alive indefinitely
tail -f /dev/null
