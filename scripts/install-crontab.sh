#!/bin/bash
# Install crontab entries for the procurement platform
# Run once on EC2 after deployment: sudo bash scripts/install-crontab.sh
#
# Requires: cronie installed and crond running
#   sudo dnf install -y cronie
#   sudo systemctl enable crond && sudo systemctl start crond

set -euo pipefail

SCRIPT_DIR=/opt/procurement-intel/scripts

# Verify scripts exist
for script in nightly-scrape.sh docker-prune.sh; do
  if [ ! -f "$SCRIPT_DIR/$script" ]; then
    echo "ERROR: $SCRIPT_DIR/$script not found. Deploy scripts first."
    exit 1
  fi
done

# Install crontab (replaces existing crontab for this user)
crontab - <<'CRONTAB'
CRON_TZ=America/Toronto

# Nightly scrape at 2 AM ET
0 2 * * * /opt/procurement-intel/scripts/nightly-scrape.sh

# Weekly Docker cleanup at 4 AM ET on Sundays
0 4 * * 0 /opt/procurement-intel/scripts/docker-prune.sh
CRONTAB

echo "Crontab installed successfully:"
crontab -l
