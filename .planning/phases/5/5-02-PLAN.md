---
phase: 5-scheduling-and-hardening
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/nightly-scrape.sh
  - scripts/docker-prune.sh
  - scripts/install-crontab.sh
autonomous: true
requirements:
  - INFR-05

must_haves:
  truths:
    - "nightly-scrape.sh uses flock -n for overlap protection"
    - "nightly-scrape.sh uses docker compose exec -T (no TTY) to invoke the scraper"
    - "nightly-scrape.sh wraps the python command with xvfb-run for Chromium display"
    - "nightly-scrape.sh runs listing retention cleanup after scraping (DELETE WHERE closing_date < 1 year)"
    - "nightly-scrape.sh logs timestamped output to /opt/procurement-intel/logs/nightly-scrape.log"
    - "docker-prune.sh runs docker system prune -f with until=168h filter"
    - "install-crontab.sh sets CRON_TZ=America/Toronto and schedules nightly scrape at 2 AM"
    - "install-crontab.sh schedules weekly Docker prune at 4 AM Sunday"
  artifacts:
    - path: "scripts/nightly-scrape.sh"
      provides: "Nightly scrape script with flock, retention cleanup"
      contains: "flock"
    - path: "scripts/docker-prune.sh"
      provides: "Weekly Docker cleanup script"
      contains: "docker system prune"
    - path: "scripts/install-crontab.sh"
      provides: "Crontab installation script"
      contains: "CRON_TZ=America/Toronto"
  key_links:
    - from: "scripts/nightly-scrape.sh"
      to: "docker-compose.yml"
      via: "docker compose exec -T scraper"
      pattern: "docker compose exec"
    - from: "scripts/install-crontab.sh"
      to: "scripts/nightly-scrape.sh"
      via: "crontab entry pointing to script path"
      pattern: "nightly-scrape.sh"
---

<objective>
Create the scheduling scripts: nightly scrape with flock overlap protection and listing retention cleanup, weekly Docker prune, and a crontab installation helper. These scripts are deployed to /opt/procurement-intel/scripts/ on EC2.

Purpose: The scraper runs automatically at 2 AM ET every night without manual intervention. Old listings are cleaned up. Docker disk usage is bounded.

Output: Three executable scripts ready for EC2 deployment. Running install-crontab.sh sets up the full schedule.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/5/5-CONTEXT.md
@.planning/phases/5/5-RESEARCH.md
@docker-compose.yml
@docker-compose.prod.yml
@scraper/main.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Nightly scrape script with flock and retention cleanup</name>
  <files>
    scripts/nightly-scrape.sh
  </files>
  <action>
    1. Create `scripts/nightly-scrape.sh`:

    ```bash
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
        python main.py

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
    ```

    2. Make executable: `chmod +x scripts/nightly-scrape.sh`

    Key design decisions:
    - `flock -n` exits with code 1 if lock cannot be acquired (non-blocking). Lock auto-releases when process exits, even on crash.
    - `-T` flag prevents "the input device is not a TTY" error in cron.
    - Each exec invocation wraps its own `xvfb-run` because DISPLAY is per-process-tree, not shared from container PID 1.
    - Retention cleanup runs unconditionally — even if scraper fails, old listings should still be cleaned up.
    - Uses `$COMPOSE` variable to always include the prod overlay.
  </action>
  <verify>
    <automated>bash -n /Users/clawbot/dev/scripts/nightly-scrape.sh && echo "nightly-scrape.sh syntax OK" && grep -q "flock -n" /Users/clawbot/dev/scripts/nightly-scrape.sh && echo "flock present" && grep -q "exec -T" /Users/clawbot/dev/scripts/nightly-scrape.sh && echo "-T flag present" && grep -q "xvfb-run" /Users/clawbot/dev/scripts/nightly-scrape.sh && echo "xvfb-run present" && grep -q "INTERVAL '1 year'" /Users/clawbot/dev/scripts/nightly-scrape.sh && echo "retention cleanup present"</automated>
    <manual>Verify script uses flock -n, docker compose exec -T, xvfb-run wrapper, and 1-year retention DELETE</manual>
  </verify>
  <done>
    - nightly-scrape.sh created with flock overlap protection
    - Uses docker compose exec -T (no TTY) for cron compatibility
    - Wraps scraper invocation in xvfb-run for Chromium display
    - Listing retention cleanup (closing_date > 1 year) runs after scrape
    - All output logged with timestamps to /opt/procurement-intel/logs/nightly-scrape.log
    - Uses prod compose overlay for all docker compose commands
  </done>
</task>

<task type="auto">
  <name>Task 2: Docker prune script and crontab installer</name>
  <files>
    scripts/docker-prune.sh
    scripts/install-crontab.sh
  </files>
  <action>
    1. Create `scripts/docker-prune.sh`:

    ```bash
    #!/bin/bash
    # Weekly Docker cleanup — removes old images, stopped containers, unused networks
    # Runs Sundays at 4 AM ET via cron

    LOGFILE=/opt/procurement-intel/logs/docker-prune.log

    exec >> "$LOGFILE" 2>&1
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Docker prune starting ==="

    # Prune artifacts older than 7 days; -f skips confirmation prompt
    docker system prune -f --filter "until=168h"

    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Docker prune complete ==="
    ```

    2. Create `scripts/install-crontab.sh`:

    ```bash
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
    ```

    3. Make both executable:
       ```bash
       chmod +x scripts/docker-prune.sh scripts/install-crontab.sh
       ```

    Key design decisions:
    - `CRON_TZ=America/Toronto` is the IANA timezone name. Handles DST transitions correctly. Do NOT use `ET`.
    - install-crontab.sh is idempotent — replaces the full crontab each time.
    - Scripts verify existence before installing to catch deployment errors.
    - Docker prune uses `--filter "until=168h"` to only remove artifacts older than 7 days, protecting recently-built images.
  </action>
  <verify>
    <automated>bash -n /Users/clawbot/dev/scripts/docker-prune.sh && echo "docker-prune.sh syntax OK" && bash -n /Users/clawbot/dev/scripts/install-crontab.sh && echo "install-crontab.sh syntax OK" && grep -q "CRON_TZ=America/Toronto" /Users/clawbot/dev/scripts/install-crontab.sh && echo "timezone correct" && grep -q "0 2 \* \* \*" /Users/clawbot/dev/scripts/install-crontab.sh && echo "2 AM schedule present" && grep -q "0 4 \* \* 0" /Users/clawbot/dev/scripts/install-crontab.sh && echo "Sunday prune schedule present"</automated>
    <manual>Verify CRON_TZ is America/Toronto (not ET), scrape at 0 2 * * *, prune at 0 4 * * 0</manual>
  </verify>
  <done>
    - docker-prune.sh prunes Docker artifacts older than 7 days weekly
    - install-crontab.sh installs full crontab with CRON_TZ=America/Toronto
    - Nightly scrape scheduled at 2 AM ET (0 2 * * *)
    - Weekly Docker prune scheduled at 4 AM ET Sundays (0 4 * * 0)
    - install-crontab.sh validates scripts exist before installing
    - All scripts executable
  </done>
</task>

</tasks>

<verification>
1. `bash -n scripts/nightly-scrape.sh` passes (valid bash syntax)
2. `bash -n scripts/docker-prune.sh` passes (valid bash syntax)
3. `bash -n scripts/install-crontab.sh` passes (valid bash syntax)
4. nightly-scrape.sh uses flock -n, docker compose exec -T, xvfb-run, and 1-year retention DELETE
5. install-crontab.sh uses CRON_TZ=America/Toronto (not ET)
6. Cron schedule: scrape at 0 2 * * *, prune at 0 4 * * 0
7. All scripts use prod compose overlay (docker compose -f ... -f ...)
</verification>

<success_criteria>
- Nightly scrape script handles flock overlap protection, TTY-free exec, Xvfb display, and listing retention
- Docker prune script cleans artifacts older than 7 days weekly
- Crontab installer sets correct timezone and schedules
- All scripts have valid bash syntax and are executable
</success_criteria>

<output>
After completion, create `.planning/phases/5/5-02-SUMMARY.md`
</output>
