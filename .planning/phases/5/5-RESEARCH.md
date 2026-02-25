# Phase 5: Scheduling and Hardening - Research

**Researched:** 2026-02-24
**Domain:** Linux cron scheduling, Docker Compose production hardening, database maintenance
**Confidence:** HIGH

## Summary

Phase 5 automates the scraper pipeline with a nightly cron job at 2 AM ET and hardens the Docker Compose stack for unattended production operation. The scope is deliberately narrow: cron + flock for scheduling, a `docker-compose.prod.yml` overlay for hardening, and a SQL-based listing retention cleanup. No alerting, no database backups, no monitoring infrastructure.

The existing codebase is well-positioned for this phase. The scraper already has per-portal error isolation (try/except in `process_portal`), exit code handling (exits 1 only if ALL portals fail), and audit logging via `scrape_runs`. The main change is converting the scraper container from a run-once-and-exit model to a long-lived idle container so `docker compose exec` can invoke it on demand.

**Primary recommendation:** Keep the scraper Dockerfile's CMD as `sleep infinity` (wrapped with xvfb-run for the virtual display), use EC2 host-level cron with `flock -n` for overlap protection, and use `docker compose -f docker-compose.yml -f docker-compose.prod.yml` for production deployment.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Scheduling mechanism:** EC2 cron job using `docker compose exec scraper python main.py` at 2 AM ET. Scraper container stays up (long-lived, idle between runs). Flock-based overlap protection.
- **Failure behavior:** Continue processing remaining portals on failure. Already implemented via try/except in `process_portal`.
- **Alerting:** NONE. No CloudWatch, no SNS, no yield alerts. Health page is sufficient.
- **Docker hardening:** `docker-compose.prod.yml` overlay with pinned image digests, `restart: always`, JSON-file log rotation. No other dev/prod differences.
- **Database backups:** No. Data is re-scrapeable.
- **Disk cleanup:** Docker system prune via cron.
- **Listing retention:** Delete listings with `closing_date` older than 1 year. Run after nightly scrape.

### Claude's Discretion
- Exact cron script structure and logging approach
- Log rotation size/count limits
- Retention cleanup implementation (standalone script vs integrated into scraper)
- Docker prune schedule and flags

### Deferred Ideas (OUT OF SCOPE)
None captured.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFR-05 | Automated nightly scheduling triggers scraper pipeline at 2 AM ET | Cron + flock pattern, scraper container CMD change, cron script template |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Component | Version | Purpose | Current Location |
|-----------|---------|---------|-----------------|
| cronie | Available in AL2023 repos | Cron daemon for scheduling | Already installed in `user_data.sh` |
| flock (util-linux) | 2.37.4 | Lock-based overlap protection | Pre-installed on AL2023 AMI |
| Docker Compose v2 | v2.32.4 | Container orchestration | Installed in `user_data.sh` |
| PostgreSQL 17 (pgvector) | pg17 | Database with vector support | `pgvector/pgvector:pg17` |

### No New Dependencies
This phase requires NO new libraries, packages, or tools beyond what is already provisioned. The `cronie` package is already installed in `terraform/user_data.sh` (line 17: `dnf install -y git` -- but actually cronie was installed for certbot renewal per STATE.md decision). The `flock` utility comes from `util-linux` which is pre-installed on the standard AL2023 AMI.

## Architecture Patterns

### Current Scraper Container Architecture (Must Change)

The scraper Dockerfile currently ends with:
```dockerfile
CMD ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "python", "main.py"]
```

This runs the scraper once and the container exits. For the `docker compose exec` pattern to work, the container must stay alive. Two approaches:

**Approach A (Recommended): Override CMD in docker-compose.prod.yml**
Keep the Dockerfile unchanged for dev use. Override CMD in the prod overlay:
```yaml
services:
  scraper:
    command: ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "sleep", "infinity"]
```
This keeps the Xvfb virtual display running (needed for Chromium) while the container idles. The cron job then uses `docker compose exec` to run the scraper inside this already-running container.

**Approach B: Change Dockerfile CMD directly**
Change the Dockerfile CMD to `sleep infinity` and always trigger via `docker compose exec`. This means running the scraper locally also requires explicit `exec`.

**Recommendation:** Approach A. The Dockerfile stays useful for local development (run once), and the prod overlay changes the behavior for scheduled execution.

### Cron Job Script Pattern

**File:** `/opt/procurement-intel/scripts/nightly-scrape.sh`

```bash
#!/bin/bash
# Nightly procurement scraper - triggered by cron at 2 AM ET
# Uses flock to prevent overlapping runs

LOCKFILE=/tmp/procurement-scrape.lock
LOGFILE=/opt/procurement-intel/logs/nightly-scrape.log
PROJECT_DIR=/opt/procurement-intel

exec >> "$LOGFILE" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Nightly scrape starting ==="

cd "$PROJECT_DIR" || exit 1

# Run scraper with flock (non-blocking: skip if previous run still going)
flock -n "$LOCKFILE" \
  docker compose exec -T scraper \
    xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python main.py

SCRAPE_EXIT=$?

if [ $SCRAPE_EXIT -eq 1 ]; then
  echo "WARN: flock could not acquire lock - previous run still active"
elif [ $SCRAPE_EXIT -ne 0 ]; then
  echo "ERROR: scraper exited with code $SCRAPE_EXIT"
fi

# Retention cleanup: delete listings with closing_date > 1 year old
docker compose exec -T db psql -U procurement -d procurement -c \
  "DELETE FROM listings WHERE closing_date < NOW() - INTERVAL '1 year';"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Nightly scrape complete ==="
```

**Key details:**
- `-T` flag on `docker compose exec` is CRITICAL -- without it, exec tries to allocate a TTY which fails in cron (no terminal)
- `flock -n` exits immediately with code 1 if lock cannot be acquired (non-blocking)
- The lock file is automatically released when the flock process exits (including if the script crashes)
- Logs append to a local file for debugging; primary audit trail remains `scrape_runs` table

### Crontab Entry

```cron
CRON_TZ=America/Toronto
0 2 * * * /opt/procurement-intel/scripts/nightly-scrape.sh
```

**Timezone handling:** `CRON_TZ=America/Toronto` tells cronie to interpret the schedule in Eastern Time. This correctly handles DST transitions (EST/EDT). Do NOT use `ET` as a timezone -- use the IANA timezone name `America/Toronto`.

### Docker System Prune Cron Entry

```cron
0 4 * * 0 docker system prune -f --filter "until=168h" >> /opt/procurement-intel/logs/docker-prune.log 2>&1
```

This runs weekly on Sundays at 4 AM ET, pruning images/containers/networks older than 7 days. The `-f` flag skips the confirmation prompt. The `--filter "until=168h"` ensures only old artifacts are removed, not recently-built images.

### docker-compose.prod.yml Overlay Structure

```yaml
services:
  db:
    image: pgvector/pgvector:pg17@sha256:<digest>
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  scraper:
    restart: always
    command: ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "sleep", "infinity"]
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  api:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  web:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  nginx:
    image: nginx:alpine@sha256:<digest>
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

**Usage:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Docker Compose merges the files, with the prod overlay taking precedence. This means:
- `restart: unless-stopped` in base becomes `restart: always` in prod
- Logging configuration is added (not present in base)
- Scraper CMD changes from run-once to sleep-infinity
- Pre-built images get pinned digests

**Note on locally-built images:** The `scraper`, `api`, and `web` services use `build:` directives, not pre-pulled images. Their digests are deterministic only if built from the same source. Pinning digests applies only to `db` (pgvector/pgvector:pg17) and `nginx` (nginx:alpine) which are pulled from registries.

### Getting Image Digests

To obtain the SHA256 digest for pinning:

```bash
# Pull and inspect
docker pull pgvector/pgvector:pg17
docker inspect --format='{{index .RepoDigests 0}}' pgvector/pgvector:pg17

docker pull nginx:alpine
docker inspect --format='{{index .RepoDigests 0}}' nginx:alpine
```

Or use `docker buildx imagetools inspect`:
```bash
docker buildx imagetools inspect pgvector/pgvector:pg17
docker buildx imagetools inspect nginx:alpine
```

The digest is printed as `sha256:abc123...`. Pin in the prod overlay as `image: pgvector/pgvector:pg17@sha256:abc123...`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Overlap protection | PID file checks, Python lock files | `flock -n /tmp/lockfile command` | flock is atomic, handles crashes (lock released on process exit), kernel-level |
| Scheduling | APScheduler, Python scheduler loops, systemd timers | cronie crontab with CRON_TZ | Battle-tested, already installed, no code to maintain, timezone-aware |
| Log rotation | Custom log rotation scripts, logrotate configs | Docker json-file driver `max-size`/`max-file` | Managed by Docker daemon, per-container, zero config beyond compose |
| Keep-alive container | Custom health-check loops, supervisor | `sleep infinity` | Simplest possible approach, zero CPU when idle |

**Key insight:** Every piece of this phase uses existing OS and Docker primitives. No application code is needed for scheduling, overlap protection, or log management.

## Common Pitfalls

### Pitfall 1: Missing `-T` Flag on `docker compose exec` in Cron
**What goes wrong:** `docker compose exec` allocates a pseudo-TTY by default. When run from cron (no terminal), this causes `the input device is not a TTY` error and the command fails silently.
**Why it happens:** Interactive terminal assumption baked into exec's defaults.
**How to avoid:** Always use `docker compose exec -T` in scripts and cron jobs.
**Warning signs:** Cron job runs but scraper never executes; no output in logs.

### Pitfall 2: Xvfb Not Running in Sleep-Infinity Container
**What goes wrong:** If the container CMD is just `sleep infinity` (without `xvfb-run`), the `docker compose exec` scraper command fails because Chromium needs a virtual display.
**Why it happens:** `xvfb-run` wraps the process and provides `DISPLAY=:99`. Without it, Chromium crashes with "no display" errors.
**How to avoid:** The container CMD must be `xvfb-run ... sleep infinity` so the virtual framebuffer is running when exec'd into. The exec command then invokes `python main.py` directly (Xvfb is already available in the container's environment from the parent process).
**CORRECTION:** Actually, `xvfb-run` sets up the display only for its child process. If CMD is `xvfb-run sleep infinity`, the display exists only for the `sleep` process. The `exec`'d process needs its own `xvfb-run` wrapper. So the exec command should be: `docker compose exec -T scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python main.py`
**Warning signs:** Chromium launch errors mentioning DISPLAY or X11.

### Pitfall 3: Cron Timezone Misconfiguration
**What goes wrong:** Cron runs at 2 AM UTC instead of 2 AM ET, or DST transitions cause runs at unexpected times.
**Why it happens:** Using `ET` (not a valid IANA timezone) or setting `TZ` instead of `CRON_TZ` (TZ only affects scripts, not cron schedule interpretation).
**How to avoid:** Use `CRON_TZ=America/Toronto` at the top of the crontab. Verify with `date` after setting.
**Warning signs:** Listings appear at unexpected times; 1-hour shift when DST changes.

### Pitfall 4: Docker Compose File Path in Cron
**What goes wrong:** Cron jobs run with minimal PATH and no working directory context. `docker compose` may not be found, or the compose file not located.
**Why it happens:** Cron has a stripped-down environment (PATH=/usr/bin:/bin).
**How to avoid:** Use absolute paths: `cd /opt/procurement-intel` and full path to docker compose binary. The script should set `PATH` or use absolute paths for `docker` and `docker compose`.
**Warning signs:** "command not found" or "no configuration file" errors in cron mail.

### Pitfall 5: Listing Retention Deleting Active Listings
**What goes wrong:** The retention query deletes listings that have NULL closing_date (comparing NULL < threshold is always false in SQL, so this is actually safe by default).
**Why it happens:** `WHERE closing_date < NOW() - INTERVAL '1 year'` only matches rows where closing_date is NOT NULL and older than 1 year. NULL closing_dates are excluded because NULL comparisons return NULL (not true).
**How to avoid:** This is a non-issue with the standard SQL comparison, but document it explicitly so future maintainers don't add `OR closing_date IS NULL` thinking it's a bug.
**Warning signs:** None -- the default behavior is correct.

### Pitfall 6: flock Lock File Location
**What goes wrong:** Lock file created in a directory that doesn't exist, or on a filesystem that doesn't support file locking.
**Why it happens:** Using a path like `/var/lock/` that may not exist, or a network filesystem.
**How to avoid:** Use `/tmp/procurement-scrape.lock` -- `/tmp` always exists and supports flock on local filesystems.
**Warning signs:** flock silently fails to acquire lock.

## Code Examples

### Listing Retention Cleanup SQL

```sql
-- Delete listings with closing_date more than 1 year ago
-- Safe: NULL closing_dates are NOT deleted (NULL < threshold = NULL, not TRUE)
-- The listings_closing_date_idx index (from 001_initial_schema.sql) covers this query
DELETE FROM listings
WHERE closing_date < NOW() - INTERVAL '1 year';
```

**Index coverage:** `CREATE INDEX listings_closing_date_idx ON listings (closing_date);` from `001_initial_schema.sql` line 65. This B-tree index supports range scans on `closing_date`, so the DELETE will be index-assisted.

**Table:** `listings` (from `001_initial_schema.sql`)
**Column:** `closing_date TIMESTAMPTZ` (nullable, line 38)
**Related column:** `original_closing_date TIMESTAMPTZ` (added in `004_search_layer.sql`) -- retention should check `closing_date` not `original_closing_date` since `closing_date` reflects the actual deadline.

### Crontab Installation

```bash
# On EC2 as ec2-user (or root)
# Ensure cronie is installed and running
sudo dnf install -y cronie
sudo systemctl enable crond
sudo systemctl start crond

# Install crontab
crontab -l 2>/dev/null; echo "
CRON_TZ=America/Toronto
# Nightly scrape at 2 AM ET
0 2 * * * /opt/procurement-intel/scripts/nightly-scrape.sh
# Weekly Docker cleanup at 4 AM ET on Sundays
0 4 * * 0 /opt/procurement-intel/scripts/docker-prune.sh
" | crontab -
```

### Docker Prune Script

```bash
#!/bin/bash
# Weekly Docker cleanup - removes old images, stopped containers, unused networks
LOGFILE=/opt/procurement-intel/logs/docker-prune.log
exec >> "$LOGFILE" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Docker prune starting ==="
docker system prune -f --filter "until=168h"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') Docker prune complete ==="
```

### Production Startup Command

```bash
# On EC2, in /opt/procurement-intel
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Verifying the Scraper Container Stays Alive

```bash
# After starting with prod overlay
docker compose ps scraper
# Should show: STATUS = Up (not Exited)

# Manual test of exec pattern
docker compose exec -T scraper xvfb-run --auto-servernum \
  --server-args="-screen 0 1920x1080x24" python main.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| cronie default on AL2 | cronie optional on AL2023 (systemd timers recommended) | 2023 | Must explicitly install cronie; could use systemd timers but cronie is simpler for this use case |
| docker-compose.override.yml (v1) | `docker compose -f ... -f ...` explicit merge (v2) | Docker Compose v2 | Override file must be explicitly specified in prod; auto-load only for `.override.yml` |
| `restart: always` + no log limits | `restart: always` + json-file log rotation | Best practice | Without log rotation, json-file logs grow unbounded until disk is full |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `/Users/clawbot/dev/pytest.ini` |
| Quick run command | `cd /Users/clawbot/dev && python -m pytest scraper/tests/ -x -q` |
| Full suite command | `cd /Users/clawbot/dev && python -m pytest -x -q` |
| Estimated runtime | ~5 seconds (unit tests only, mocked DB) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFR-05 | Nightly cron triggers scraper at 2 AM ET | manual-only | Verify crontab installed on EC2 | N/A (infrastructure) |
| INFR-05 (sub) | docker-compose.prod.yml merges correctly | smoke | `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` | No test file needed -- compose config validation |
| INFR-05 (sub) | Scraper container stays alive with sleep infinity | smoke | `docker compose -f ... -f ... up -d scraper && docker compose ps scraper` | No test file needed -- manual verification |
| INFR-05 (sub) | Listing retention SQL deletes old listings | unit | `pytest scraper/tests/test_retention.py -x` | No -- Wave 0 gap |
| INFR-05 (sub) | flock prevents overlapping runs | manual-only | Run two instances of nightly-scrape.sh simultaneously | N/A (infrastructure) |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task, run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet` to validate compose merge
- **Full suite trigger:** Before merging final task: full pytest suite + manual EC2 verification
- **Phase-complete gate:** Crontab installed on EC2, scraper container stays alive, manual trigger produces listings
- **Estimated feedback latency per task:** ~2 seconds (compose config validation)

### Wave 0 Gaps (must be created before implementation)
- [ ] None critical -- this phase is primarily infrastructure (scripts, compose overlays, crontab). The retention SQL can be tested via a simple unit test but is optional given the single-line DELETE statement.

## Open Questions

1. **Exact image digests for pinning**
   - What we know: Need digests for `pgvector/pgvector:pg17` and `nginx:alpine`. Locally-built images (scraper, api, web) don't need digest pinning since they're built from source.
   - What's unclear: Digests change with each image release. Must be fetched at implementation time on the EC2 instance.
   - Recommendation: Fetch digests during plan execution using `docker pull` + `docker inspect` and pin in `docker-compose.prod.yml`. Document the process so digests can be updated periodically.

2. **cronie installation status on EC2**
   - What we know: `user_data.sh` does NOT install cronie. But STATE.md mentions "cronie installed on EC2 for certbot renewal cron" from Phase 1.
   - What's unclear: Whether cronie was installed manually on the running instance or if user_data.sh was updated and we're seeing a stale file.
   - Recommendation: The implementation should include `dnf install -y cronie` in the setup script regardless (idempotent). Also update `user_data.sh` to include it for fresh deployments.

3. **Scraper container Xvfb for exec**
   - What we know: `xvfb-run` sets DISPLAY only for its child process tree. The `docker compose exec` command spawns a NEW process, not a child of the container's PID 1.
   - What's unclear: Whether Xvfb from the CMD's `xvfb-run sleep infinity` makes the display available to exec'd processes.
   - Recommendation: The exec command itself must include `xvfb-run` to start its own virtual display. This works because multiple Xvfb instances can coexist using `--auto-servernum`. Alternatively, just use `sleep infinity` as CMD (no xvfb-run wrapper) and always wrap exec commands with `xvfb-run`.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `scraper/main.py` -- exit code handling (exits 1 only if ALL portals fail, line 133)
- Codebase inspection: `scraper/Dockerfile` -- current CMD is xvfb-run + python main.py
- Codebase inspection: `scraper/pipeline/orchestrator.py` -- per-portal error isolation confirmed (try/except line 88-144)
- Codebase inspection: `docker-compose.yml` -- current services, restart policies, image tags
- Codebase inspection: `db/migrations/001_initial_schema.sql` -- `closing_date TIMESTAMPTZ` column, `listings_closing_date_idx` index
- Codebase inspection: `terraform/user_data.sh` -- EC2 provisioning script, Docker/Compose installation
- AWS docs: Amazon Linux 2023 image comparison -- `util-linux 2.37.4` pre-installed on standard AMI (provides `flock`)

### Secondary (MEDIUM confidence)
- [Docker Docs: Configure logging drivers](https://docs.docker.com/engine/logging/configure/) -- json-file driver options
- [Docker Docs: Image digests](https://docs.docker.com/dhi/core-concepts/digests/) -- SHA256 pinning approach
- [AWS Docs: AL2023 cron deprecation](https://docs.aws.amazon.com/linux/al2023/ug/cron.html) -- cronie available but not default
- [Docker Compose override patterns](https://docker.recipes/docs/compose-overrides) -- file merge behavior

### Tertiary (LOW confidence)
- [WebSearch: flock usage in cron](https://www.linuxbash.sh/post/use-flock-to-prevent-concurrent-script-execution) -- flock pattern verified against multiple sources
- [WebSearch: CRON_TZ behavior](https://thelinuxcode.com/set-timezone-crontab/) -- CRON_TZ vs TZ distinction

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all components already in project or pre-installed on AL2023
- Architecture: HIGH - patterns are standard Linux/Docker practices, verified against codebase
- Pitfalls: HIGH - Xvfb/TTY/timezone issues are well-documented failure modes
- Retention SQL: HIGH - schema inspected directly, index confirmed

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable infrastructure patterns, no fast-moving dependencies)
