---
phase: quick-4
plan: 01
subsystem: infra
tags: [ec2, docker, postgres, migration, deployment]

# Dependency graph
requires:
  - phase: quick-2
    provides: "Migration 006 enabling MERX portals"
  - phase: quick-3
    provides: "Migration 007 updating Nova Scotia URL"
provides:
  - "All 63 portals enabled in production database"
  - "Migration files 006 and 008 synced to EC2"
  - "Full deployment verification (containers, code, data)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: ["SCP migration sync for non-git EC2 deployments"]

key-files:
  created: []
  modified:
    - "db/migrations/006_enable_merx_portals.sql (synced to EC2)"
    - "db/migrations/008_enable_all_portals.sql (synced to EC2)"

key-decisions:
  - "EC2 is not a git repo -- used SCP to sync migration files instead of git pull"
  - "All 63 portals were already enabled (migration 008 effect pre-applied) -- verified rather than re-applied"

patterns-established: []

requirements-completed: [QT-009]

# Metrics
duration: 2min
completed: 2026-02-26
---

# Quick Task 4: Enable All Disabled Portals and Deploy Summary

**All 63 portals verified enabled in production via SQL query and --list-portals; migration files 006/008 synced to EC2 via SCP**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-26T15:09:50Z
- **Completed:** 2026-02-26T15:14:00Z
- **Tasks:** 2 (1 auto + 1 human-verify)
- **Files modified:** 2 (remote only -- migration files synced to EC2)

## Accomplishments
- Verified all 63 portals show `enabled=true` in production database (total=63, enabled=63, disabled=0)
- Synced missing migration files (006_enable_merx_portals.sql, 008_enable_all_portals.sql) to EC2 via SCP
- Confirmed all 5 Docker containers running: db (healthy), scraper, api, web, nginx
- Verified latest code deployed: page.evaluate() fix present in browser_scraper.py, Nova Scotia URL updated
- Verified keywords_library.csv has 55 keywords (56 lines with header)
- Human-verified: Edmonton Procurement test scrape completed successfully (0 errors)

## Task Commits

1. **Task 1: Deploy latest code and apply migrations to production** - no local commit (remote-only deployment via SSH/SCP)
2. **Task 2: Verify deployment and portal status** - human-verified and approved

**Plan metadata:** see final commit below

## Files Created/Modified
- `db/migrations/006_enable_merx_portals.sql` - Synced to EC2 (was missing from remote)
- `db/migrations/008_enable_all_portals.sql` - Synced to EC2 (was missing from remote)

## Decisions Made
- **EC2 not a git repo:** The production deployment at `/opt/procurement-intel` does not have a `.git` directory. Used `scp` to copy missing migration files directly rather than attempting `git pull`. This is consistent with prior deployment patterns.
- **Migration already applied:** All 63 portals were already enabled in production (SEAO, Alberta, Edmonton all showing `enabled=t`). The migration 008 effect had been applied previously (likely during the QT-007 session when SEAO/Alberta/Edmonton portals were enabled alongside MERX). Verified state rather than re-applying.
- **No container rebuild needed:** All containers running latest code -- browser_scraper.py has page.evaluate() fix, scraper pipeline files match local, keywords CSV is current.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] EC2 has no .git directory -- used SCP instead of git pull**
- **Found during:** Task 1 (deploy latest code)
- **Issue:** Plan assumed `git pull origin main` on EC2, but `/opt/procurement-intel` is not a git repo (no `.git` directory)
- **Fix:** Used `scp` to copy the 2 missing migration files (006, 008) directly to EC2
- **Files modified:** EC2: `/opt/procurement-intel/db/migrations/006_enable_merx_portals.sql`, `/opt/procurement-intel/db/migrations/008_enable_all_portals.sql`
- **Verification:** `ls -la /opt/procurement-intel/db/migrations/` shows all 8 migration files present
- **Committed in:** N/A (remote deployment, no local code changes)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal -- SCP achieves the same result as git pull for syncing migration files. No scope creep.

## Issues Encountered
- EC2 deployment is not a git repository, so `git pull` fails. This is a known infrastructure characteristic -- production files are deployed via copy/SCP rather than git clone. Future deployment plans should use SCP or rsync commands instead of git operations.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 63 portals enabled and ready for nightly cron scraping
- Edmonton Procurement test scrape verified functional (0 errors)
- Nightly cron will automatically pick up all newly-enabled portals on next run
- Portals with `requires_login=true` (SEAO family, Alberta, Edmonton) may hit login walls during scraping -- this is expected and handled gracefully by the scraper

## Self-Check: PASSED

- FOUND: `.planning/quick/4-enable-all-disabled-portals-and-deploy-t/4-SUMMARY.md`
- FOUND: `.planning/quick/4-enable-all-disabled-portals-and-deploy-t/4-PLAN.md`
- FOUND: `db/migrations/006_enable_merx_portals.sql`
- FOUND: `db/migrations/008_enable_all_portals.sql`
- Production verified: 63/63 portals enabled, 5/5 containers running

---
*Quick Task: 4-enable-all-disabled-portals-and-deploy-t*
*Completed: 2026-02-26*
