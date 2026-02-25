---
phase: 4
plan: 03
subsystem: web
tags: [nextjs, shadcn-ui, sheet, listing-detail, new-badge, freshness, last-visited-at]

# Dependency graph
requires:
  - phase: 4
    plan: 01
    provides: Next.js scaffold with Auth.js, dashboard shell, TypeScript types, API client utils, format helpers, shadcn Sheet component
  - phase: 4
    plan: 02
    provides: Search page with URL state, result cards with isNew prop, ResultsList with lastVisitedAt comparison logic
provides:
  - Listing detail Sheet slide-out panel with full detail view (documents, contacts, source link)
  - useListingDetail hook with AbortController cleanup
  - "New" badge logic using read-before-update last_visited_at pattern
  - Data freshness indicator in nav bar with 5-minute auto-refresh
  - SessionProvider wrapper for useSession in dashboard client components
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [Sheet slide-out from right for listing detail with ScrollArea, read-before-update pattern for last_visited_at to preserve badge state, SessionProvider wrapper at dashboard layout level for useSession, Nav children slot for extensible nav content]

key-files:
  created:
    - web/src/hooks/use-listing-detail.ts
    - web/src/components/search/listing-detail.tsx
    - web/src/components/layout/freshness.tsx
    - web/src/components/layout/session-wrapper.tsx
  modified:
    - web/src/app/dashboard/page.tsx
    - web/src/app/dashboard/layout.tsx
    - web/src/components/layout/nav.tsx

key-decisions:
  - "Sheet slide-out from right with sm:max-w-[600px] for listing detail -- results list stays visible behind overlay"
  - "Read-before-update pattern: GET last_visited_at THEN PUT to update -- stored previous value used for New badge comparison throughout session"
  - "SessionProvider at dashboard layout level wraps all dashboard pages for useSession access"
  - "Nav accepts children prop for extensible content like freshness indicator"
  - "ScrollArea wraps Sheet body for long listing content scrolling"

patterns-established:
  - "Detail panel pattern: Sheet + useListingDetail hook + selectedId state in parent page"
  - "Badge computation pattern: ResultsList computes isNew from lastVisitedAt vs posting_date, passes to ResultCard"
  - "Freshness polling pattern: fetch on mount + setInterval for periodic refresh"

requirements-completed: [DASH-02, DASH-03, DASH-05, DASH-06, DASH-09]

# Metrics
duration: 3min
completed: 2026-02-24
---

# Phase 4 Plan 03: Listing Detail Sheet, New Badges, Data Freshness Summary

**Sheet slide-out panel with locked layout order (title, status, dates, metadata, description, documents, contact card, source link), read-before-update New badge logic via last_visited_at, and nav bar freshness indicator with 5-minute polling**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T02:46:24Z
- **Completed:** 2026-02-25T02:49:20Z
- **Tasks:** 2
- **Files created/modified:** 7

## Accomplishments

- useListingDetail hook fetching listing detail by ID with AbortController cleanup and null-clearing on deselection
- ListingDetailSheet component (250+ lines) with locked layout order: title, status badge (color-coded), portal name, dates grid, metadata (province, value, classification codes), description, documents with download links, contact card with mailto/tel links, prominent "View on Source Portal" button
- All missing values show explicit labels: "Not specified", "Value not disclosed", "No documents available", "No contact information available", "Source URL not available"
- Documents rendered as clickable cards with FileText icon, type badge, date, and external link icon
- Contact card with actionable email (mailto:) and phone (tel:) links highlighted in blue
- "View on Source Portal" as a full-width lg Button, not a small link -- disabled state when source_url is null
- Loading state shows Skeleton components in Sheet layout
- Data freshness indicator component fetching /api/health/freshness on mount with 5-minute auto-refresh interval
- SessionProvider wrapper component for Auth.js v5 useSession in dashboard client components
- Read-before-update last_visited_at pattern: GET previous value, store in state, THEN PUT to update -- previous value used for "New" badge comparison
- Nav component extended with children prop to accept freshness indicator alongside sign out button
- Dashboard page wired with selectedListingId state, useListingDetail hook, useSession for user ID, and lastVisitedAt for badge computation

## Task Commits

1. **Task 1: Listing detail Sheet slide-out** - `4f27590` (feat)
2. **Task 2: New badges + data freshness indicator** - `9793b6d` (feat)

## Files Created/Modified

### Task 1
- `web/src/hooks/use-listing-detail.ts` - Client-side hook fetching listing detail with AbortController
- `web/src/components/search/listing-detail.tsx` - Sheet slide-out with full listing detail in locked layout order
- `web/src/app/dashboard/page.tsx` - Wired selectedListingId state, useListingDetail, ListingDetailSheet, useSession, lastVisitedAt

### Task 2
- `web/src/components/layout/freshness.tsx` - Data freshness indicator with 5-min polling
- `web/src/components/layout/session-wrapper.tsx` - SessionProvider client wrapper
- `web/src/app/dashboard/layout.tsx` - Added SessionWrapper and Freshness to layout
- `web/src/components/layout/nav.tsx` - Added children prop for nav extensibility

## Verification Results

1. `npx tsc --noEmit` -- compiled successfully, zero TypeScript errors
2. `npm run build` -- compiled successfully, all 6 routes generated (static + dynamic)
3. Listing detail layout verified: title -> status -> portal -> dates -> metadata -> description -> documents -> contact -> source link
4. Missing value labels verified: "Not specified", "Value not disclosed", "No documents available", "No contact information available", "Source URL not available"
5. Read-before-update pattern verified: GET /users/{id}/last-visit -> store previous -> PUT /users/{id}/last-visit -> use previous for badges
6. ResultCard already renders emerald "New" badge when isNew=true (verified from 4-02)
7. ResultsList already computes isNew from lastVisitedAt vs posting_date (verified from 4-02)

## Decisions Made

- Sheet slide-out from right with sm:max-w-[600px] overriding default sm:max-w-sm for adequate detail display width
- Read-before-update pattern ensures New badges persist during the current session (not cleared on page load)
- SessionProvider at dashboard layout level (not root) to scope session to authenticated pages only
- Nav children prop keeps the component flexible without requiring modifications for future nav additions
- ScrollArea wraps the sheet body content for consistent scrolling behavior on long listings

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Created SessionWrapper client component**
- **Found during:** Task 2 implementation
- **Issue:** Dashboard layout is a server component but SessionProvider is a client component -- cannot use directly
- **Fix:** Created `session-wrapper.tsx` client component wrapping SessionProvider, imported in server layout
- **Files created:** web/src/components/layout/session-wrapper.tsx
- **Commit:** 9793b6d

**2. [Rule 2 - Missing functionality] Added children prop to Nav component**
- **Found during:** Task 2 implementation
- **Issue:** Nav component had no way to inject the freshness indicator without modifying its internals
- **Fix:** Added optional children prop to Nav, rendered in a flex container alongside sign out button
- **Files modified:** web/src/components/layout/nav.tsx
- **Commit:** 9793b6d

## Issues Encountered

None.

## Next Phase Readiness

- All 4 Phase 4 plans now complete (4-01 scaffold, 4-02 search, 4-03 detail+badges, 4-04 health)
- Dashboard provides complete search workflow: browse -> filter -> click -> evaluate -> act (via source link)
- Phase 4 success criteria fully addressed:
  1. Login + browse + filter + persistent auth (4-01 + 4-02)
  2. Listing detail with documents, contacts, source link (4-03)
  3. New badges on fresh listings (4-03)
  4. URL-encoded shareable search state (4-02)
  5. Scraper health page + data freshness indicator (4-04 + 4-03)

## Self-Check: PASSED

All 7 created/modified files verified present. Both task commits (4f27590, 9793b6d) verified in git log.

---
*Phase: 4*
*Completed: 2026-02-24*
