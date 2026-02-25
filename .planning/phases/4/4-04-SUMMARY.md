---
phase: 4
plan: 04
subsystem: web, docker
tags: [nextjs, react, tailwind, shadcn-ui, docker, health-dashboard]

# Dependency graph
requires:
  - phase: 4
    plan: 01
    provides: Next.js scaffold, Auth.js auth, PortalHealth type, fetchApi, formatDate, Nav with Health link
provides:
  - Scraper health page at /dashboard/health with per-portal status table
  - StatusBadge with locked staleness thresholds (healthy/warning/stale/unknown/running)
  - PortalTable with 10 columns, status sorting, skeleton loading
  - usePortalHealth hook with 60-second auto-refresh
  - Multi-stage Docker standalone Dockerfile for Next.js
  - Docker Compose web service with API_INTERNAL_URL and NEXTAUTH_URL
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [usePortalHealth client-side fetch hook with auto-refresh, StatusBadge staleness threshold logic, multi-stage Docker standalone build for Next.js]

key-files:
  created:
    - web/src/hooks/use-portal-health.ts
    - web/src/components/health/status-badge.tsx
    - web/src/components/health/portal-table.tsx
    - web/src/app/dashboard/health/page.tsx
    - web/Dockerfile
  modified:
    - api/routers/portal_health.py
    - web/src/types/health.ts
    - docker-compose.yml

key-decisions:
  - "Staleness thresholds locked: healthy (<3 fails, <7 days), warning (3+ fails), stale (7+ days), unknown (no runs), running"
  - "Health page is purely informational with no action buttons"
  - "Multi-stage Docker build copies standalone + static + public to runner stage"
  - "Added level/province to API portal_health query for health table columns"

requirements-completed: [DASH-07]

# Metrics
duration: 3min
completed: 2026-02-24
---

# Phase 4 Plan 04: Scraper Health Page and Docker Standalone Build Summary

**Per-portal health table with staleness badges (healthy/warning/stale), 60s auto-refresh, and multi-stage Next.js Docker standalone build for deployment**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T02:38:06Z
- **Completed:** 2026-02-25T02:41:05Z
- **Tasks:** 2
- **Files created/modified:** 8

## Accomplishments

- Scraper health page at /dashboard/health with per-portal status table
- StatusBadge component with 5 status levels: healthy (green), warning/amber (3+ recent failures), stale/red (7+ days since success), unknown (gray, no runs), running (blue)
- PortalTable with 10 columns: status badge, portal name (external link), level (federal/provincial/municipal badges), province, last run date, last status with icon, listings count, recent failure rate, duration, error message with tooltip
- Default sort by status severity (stale > warning > healthy), then alphabetical
- Skeleton loading state and summary statistics (total, healthy, warnings, errors)
- usePortalHealth hook with 60-second auto-refresh interval
- Multi-stage Dockerfile: deps (npm ci) -> builder (next build) -> runner (standalone with non-root user)
- Docker Compose web service updated with API_INTERNAL_URL=http://api:8000 and NEXTAUTH_URL, depends_on api + db

## Task Commits

1. **Task 1: Scraper health page with portal table and staleness badges** - `bc8924f` (feat)
2. **Task 2: Docker standalone build and compose integration** - `745af70` (chore)

## Files Created/Modified

### Health Page (Task 1)
- `web/src/hooks/use-portal-health.ts` - Client-side fetch hook with 60s auto-refresh
- `web/src/components/health/status-badge.tsx` - StatusBadge + getPortalStatus helper + STATUS_SORT_ORDER
- `web/src/components/health/portal-table.tsx` - 10-column table with sorting, loading, tooltips
- `web/src/app/dashboard/health/page.tsx` - Health page with title, error display, PortalTable
- `api/routers/portal_health.py` - Added p.level, p.province to portal_health query
- `web/src/types/health.ts` - Added level, province fields to PortalHealth interface

### Docker (Task 2)
- `web/Dockerfile` - Multi-stage standalone build (deps -> builder -> runner)
- `docker-compose.yml` - Updated web service with environment vars and api dependency

## Verification Results

1. TypeScript compilation: `tsc --noEmit` passes with zero errors
2. Docker Compose: `docker compose config` validates successfully
3. Dockerfile: 3 stages (deps, builder, runner), copies standalone + static + public
4. API_INTERNAL_URL=http://api:8000 present in docker-compose web environment

## Decisions Made

- Staleness thresholds locked as specified: healthy (last success <7 days AND <3 recent failures), warning (3+ failures in last 5 runs), stale (7+ days since last success or never succeeded), unknown (no runs), running (current run in progress)
- Health page is purely informational -- no retry/disable/enable buttons
- Multi-stage Docker build copies three artifacts to runner: .next/standalone, .next/static, public/
- Non-root nextjs user (uid 1001) in Docker runner for security
- Added level and province to API query and TypeScript type (deviation from original API, needed for table columns)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Added level/province to portal_health API query**
- **Found during:** Task 1
- **Issue:** The API /health/portals endpoint did not include p.level or p.province from the portals table, but the health table requires Level and Province columns
- **Fix:** Added `p.level, p.province` to the SQL SELECT in portal_health.py and added `level` and `province` fields to the PortalHealth TypeScript interface
- **Files modified:** api/routers/portal_health.py, web/src/types/health.ts
- **Commit:** bc8924f

## Issues Encountered

None.

## Next Phase Readiness

- All Phase 4 UI components are now complete (search, listing detail, health)
- Full Docker stack is deployable with `docker compose up`
- Next.js standalone build ready for production deployment

## Self-Check: PASSED

All 8 created/modified files verified present. Both task commits (bc8924f, 745af70) verified in git log.

---
*Phase: 4*
*Completed: 2026-02-24*
