---
phase: 4
plan: 01
subsystem: api, web
tags: [fastapi, nextjs, auth.js, tailwind, shadcn-ui, bcryptjs, nuqs, postgresql]

# Dependency graph
requires:
  - phase: 3
    provides: FastAPI search API with hybrid search, listings table, portals table, scrape_runs table
provides:
  - FastAPI endpoints for listing detail, portal health, freshness, user auth, last-visit tracking
  - Users table migration with 3 seed accounts (bcrypt hashed)
  - Next.js 16 project scaffold with TypeScript, Tailwind CSS, shadcn/ui
  - Auth.js v5 credentials authentication with JWT sessions
  - Login page with form validation and error handling
  - Protected dashboard shell with nav bar
  - TypeScript types for search, listing, and health API contracts
  - API client utilities for server-side and client-side fetch
  - Format helpers for dates, currency, and relative time
affects: [4-02, 4-03, 4-04]

# Tech tracking
tech-stack:
  added: [next.js, react, auth.js, tailwind-css, shadcn-ui, nuqs, bcryptjs, date-fns, zod, lucide-react, tanstack-react-table]
  patterns: [Auth.js v5 credentials provider with bcryptjs verification, NuqsAdapter wrapper for URL state, fetchApi typed wrapper for server components, db_connection context manager reused in new routers]

key-files:
  created:
    - db/migrations/005_users.sql
    - api/routers/listings.py
    - api/routers/portal_health.py
    - api/routers/users.py
    - web/src/auth.ts
    - web/src/middleware.ts
    - web/src/app/api/auth/[...nextauth]/route.ts
    - web/src/app/layout.tsx
    - web/src/app/page.tsx
    - web/src/app/login/page.tsx
    - web/src/app/dashboard/layout.tsx
    - web/src/app/dashboard/page.tsx
    - web/src/components/login-form.tsx
    - web/src/components/layout/nav.tsx
    - web/src/lib/api.ts
    - web/src/lib/format.ts
    - web/src/types/search.ts
    - web/src/types/listing.ts
    - web/src/types/health.ts
    - web/next.config.ts
  modified:
    - api/main.py

key-decisions:
  - "Auth.js v5 credentials provider with bcryptjs in Next.js layer (not API layer) for password verification"
  - "JWT session strategy with 30-day maxAge for persistent BD team login"
  - "Inter font replacing Geist for cleaner dashboard typography"
  - "Standalone output mode for Docker deployment readiness"
  - "NuqsAdapter at root layout level for URL-encoded search state in all pages"

patterns-established:
  - "API fetch pattern: fetchApi<T> typed wrapper with internal URL for server components"
  - "Auth pattern: middleware protecting /dashboard/* routes, /login as public signin page"
  - "Layout pattern: dashboard layout with sticky nav + max-w-7xl content area"
  - "Serialization pattern: _serialize_row helper for UUID/datetime/Decimal to JSON"

requirements-completed: []

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 4 Plan 01: API Endpoints, Users Migration, Next.js Scaffold Summary

**FastAPI listing/health/user endpoints, users migration with 3 seed accounts, and complete Next.js 16 scaffold with Auth.js v5 credentials authentication and dashboard shell**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T02:29:30Z
- **Completed:** 2026-02-25T02:33:30Z
- **Tasks:** 2
- **Files created/modified:** 47

## Accomplishments

- 5 new FastAPI endpoints: listing detail, portal health (with last-5-runs CTE aggregation), data freshness, user auth lookup, and last-visit GET/PUT
- Users table migration (005_users.sql) with 3 bcrypt-hashed seed accounts
- Complete Next.js 16 project replacing the Express stub with TypeScript + Tailwind CSS
- Auth.js v5 credentials provider authenticating against the FastAPI user endpoint with bcryptjs password verification
- Login page with form validation, error display, and loading state
- Protected /dashboard route with Auth.js middleware guard
- Dashboard layout with sticky nav bar (Search, Scraper Health, Sign out)
- 13 shadcn/ui components installed (button, input, badge, card, sheet, table, select, skeleton, separator, scroll-area, tooltip, dropdown-menu, label)
- TypeScript type definitions matching API response contracts for search, listing detail, and health
- API client utilities with typed fetch wrapper and server/client URL resolution
- Format helpers for dates, currency ranges, and relative time

## Task Commits

1. **Task 1: FastAPI endpoints + users migration** - `ad491a1` (feat)
2. **Task 2: Next.js scaffold + Auth.js + login page + dashboard shell** - `570ef7c` (feat)

## Files Created/Modified

### API (Task 1)
- `db/migrations/005_users.sql` - Users table with 3 seed accounts
- `api/routers/listings.py` - GET /listings/{listing_id} with portal JOIN and serialization
- `api/routers/portal_health.py` - GET /health/portals (CTE aggregation) + GET /health/freshness
- `api/routers/users.py` - GET /auth/user, GET/PUT /users/{user_id}/last-visit
- `api/main.py` - Added imports and include_router for listings, portal_health, users

### Web (Task 2)
- `web/next.config.ts` - Standalone output mode
- `web/src/auth.ts` - Auth.js v5 config with credentials provider
- `web/src/middleware.ts` - Route protection for /dashboard/*
- `web/src/app/api/auth/[...nextauth]/route.ts` - Auth.js route handler
- `web/src/app/layout.tsx` - Root layout with Inter font and NuqsAdapter
- `web/src/app/page.tsx` - Redirect to /dashboard
- `web/src/app/login/page.tsx` - Login page with card layout
- `web/src/app/dashboard/layout.tsx` - Dashboard layout with Nav
- `web/src/app/dashboard/page.tsx` - Placeholder dashboard page
- `web/src/components/login-form.tsx` - Client-side login form with signIn
- `web/src/components/layout/nav.tsx` - Top nav with links and sign out
- `web/src/lib/api.ts` - fetchApi typed wrapper + URL helpers
- `web/src/lib/format.ts` - formatDate, formatCurrency, formatRelativeTime
- `web/src/types/search.ts` - ListingResult, FacetCounts, SearchResponse
- `web/src/types/listing.ts` - ListingDetail, ContactInfo, Document
- `web/src/types/health.ts` - PortalHealth, FreshnessData

## Verification Results

1. Router imports: `from api.routers import listings, portal_health, users` -- OK
2. Route registration: All 6 new routes verified in app.routes -- `/listings/{listing_id}`, `/health/portals`, `/health/freshness`, `/auth/user`, `/users/{user_id}/last-visit` (GET + PUT)
3. Next.js build: `npm run build` -- compiled successfully, all 6 routes generated (static + dynamic)

## Decisions Made

- Auth.js v5 credentials provider handles password verification in the Next.js layer using bcryptjs (keeps the API stateless -- no bcrypt dependency in Python)
- JWT session strategy with 30-day maxAge provides persistent login suitable for 3-user BD team
- Inter font chosen over Geist for cleaner dashboard typography
- Standalone output mode enabled for Docker deployment
- NuqsAdapter wraps entire app at root layout level to enable URL-encoded search state

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- Dashboard shell ready for Plan 4-02 (search UI with filters, results, and URL state)
- Listing types ready for Plan 4-03 (listing detail side panel)
- Health types ready for Plan 4-04 (scraper health page)
- Auth flow complete -- all subsequent pages just need to work within the dashboard layout

## Self-Check: PASSED

All 21 created/modified files verified present. Both task commits (ad491a1, 570ef7c) verified in git log.

---
*Phase: 4*
*Completed: 2026-02-24*
