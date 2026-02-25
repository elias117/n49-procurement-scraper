---
phase: 4
plan: 02
subsystem: web
tags: [nextjs, nuqs, tailwind, shadcn-ui, search, url-state, debounce]

# Dependency graph
requires:
  - phase: 4
    plan: 01
    provides: Next.js scaffold with Auth.js, dashboard shell, TypeScript types, API client utils, format helpers
provides:
  - Search params parser definitions for all 16 search parameters (nuqs)
  - useSearch hook with URL-synced state and API fetching
  - Debounced search bar with hybrid/exact mode toggle
  - Always-visible filter sidebar with 7 filter dimensions and facet counts
  - Decision-dense result cards with explicit missing-value labels
  - Results list with skeleton loading, empty state, and "New" badge support
  - Pagination controls with 5-page window navigation
  - Sort controls with field dropdown and asc/desc toggle
  - Assembled search page at /dashboard with all components and Suspense boundary
affects: [4-03, 4-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [nuqs useQueryStates with history push for URL-encoded search state, AbortController for fetch cancellation on params change, Suspense boundary for nuqs SSR compatibility, setFilter helper resets page to 1 on any filter change]

key-files:
  created:
    - web/src/lib/search-params.ts
    - web/src/hooks/use-search.ts
    - web/src/components/search/search-bar.tsx
    - web/src/components/search/filter-sidebar.tsx
    - web/src/components/search/result-card.tsx
    - web/src/components/search/results-list.tsx
    - web/src/components/search/pagination.tsx
    - web/src/components/search/sort-controls.tsx
    - web/src/components/ui/checkbox.tsx
  modified:
    - web/src/app/dashboard/page.tsx

key-decisions:
  - "Suspense boundary wrapping DashboardContent because nuqs useQueryStates reads URL search params at render time"
  - "setFilter helper automatically resets page to 1 to prevent empty-page navigation after filter changes"
  - "AbortController cancels in-flight requests when params change to prevent stale responses"
  - "Result cards show only fields available from search API (status and classification_codes deferred to detail panel in 4-03)"

patterns-established:
  - "Search state pattern: all 16 params synced bidirectionally between URL and UI via nuqs searchParamsParsers"
  - "Filter sidebar pattern: checkbox lists with facet counts from API response, date inputs, number inputs, tag chips"
  - "Debounce pattern: local state with 300ms setTimeout syncing to URL params"
  - "Page layout pattern: flex row with w-64 sidebar left, flex-1 content right"

requirements-completed: [DASH-01, DASH-08]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 4 Plan 02: Search Page with URL State, Filters, Result Cards, Pagination Summary

**Full search page with nuqs URL-synced state for all 16 params, Amazon-style filter sidebar with facet counts, debounced search bar with hybrid/exact toggle, decision-dense result cards, skeleton loading states, and paginated sort controls**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T02:37:30Z
- **Completed:** 2026-02-25T02:41:16Z
- **Tasks:** 2
- **Files created/modified:** 10

## Accomplishments

- nuqs parser definitions covering all 16 search parameters matching the FastAPI /search endpoint exactly
- useSearch hook that syncs URL state bidirectionally, builds URLSearchParams with proper array param handling (append for FastAPI repeated query params), and fetches with AbortController cancellation
- SearchBar component with local state debounced at 300ms, hybrid/exact mode toggle, search icon, and clear button
- Amazon-style always-visible filter sidebar with 7 filter dimensions: regions (checkbox + facet counts), portals (checkbox + facet counts), posting date range, closing date range, contract value range, classification codes (tag chips), and include_closed toggle
- Decision-dense result cards showing title, source portal, province, posting date, closing date, contract value (or "Value not disclosed"), and snippet with keyword highlight support via dangerouslySetInnerHTML
- Results list with skeleton loading (6 cards), empty state messaging, total count display, and "New" badge logic based on lastVisitedAt comparison
- Pagination with first/prev/5-page-window/next/last and "Page X of Y" display
- Sort controls with dropdown (relevance, posting date, closing date, value) and asc/desc toggle
- Dashboard page assembling all components in a sidebar+content layout with Suspense boundary for SSR compatibility
- shadcn checkbox component installed for filter interactions

## Task Commits

1. **Task 1: Search params, useSearch hook, and search bar** - `0fe9118` (feat)
2. **Task 2: Filter sidebar, result cards, pagination, sort, and page assembly** - `de1154f` (feat)

## Files Created/Modified

### Task 1
- `web/src/lib/search-params.ts` - nuqs parser definitions for all 16 search parameters
- `web/src/hooks/use-search.ts` - URL-synced search state hook with API fetching and AbortController
- `web/src/components/search/search-bar.tsx` - Debounced input with hybrid/exact mode toggle

### Task 2
- `web/src/components/search/filter-sidebar.tsx` - Always-visible sidebar with 7 filter dimensions
- `web/src/components/search/result-card.tsx` - Decision-dense card with all available search fields
- `web/src/components/search/results-list.tsx` - Card list with loading skeletons and empty state
- `web/src/components/search/pagination.tsx` - Page navigation with 5-page window
- `web/src/components/search/sort-controls.tsx` - Sort field dropdown + order toggle
- `web/src/components/ui/checkbox.tsx` - shadcn checkbox component (installed)
- `web/src/app/dashboard/page.tsx` - Assembled search page with Suspense boundary

## Verification Results

1. `npx tsc --noEmit` -- compiled successfully, zero errors
2. `npm run build` -- compiled successfully, all 6 routes generated (static + dynamic)
3. All 16 search parameters defined in searchParamsParsers matching FastAPI /search endpoint
4. Array params use `append` (not `set`) for FastAPI repeated query param compatibility
5. Filter sidebar has all 7 sections: regions, portals, posting date, closing date, value range, classification codes, include_closed
6. Result cards display all available fields with explicit "Not specified" / "Value not disclosed" labels
7. URL state shareable: nuqs history "push" enables back/forward and URL copy-paste

## Decisions Made

- Suspense boundary wrapping DashboardContent for nuqs SSR compatibility (Next.js requires Suspense for useSearchParams)
- setFilter helper resets page to 1 automatically to prevent empty-page results after filter changes
- AbortController cancels in-flight requests on params change to prevent stale response display
- Result cards show only search API fields; status and classification_codes deferred to detail side panel (Plan 4-03)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added Suspense boundary for nuqs SSR compatibility**
- **Found during:** Task 2 verification (npm run build)
- **Issue:** Next.js 16 requires useSearchParams (used internally by nuqs) to be wrapped in a Suspense boundary
- **Fix:** Split DashboardPage into DashboardSkeleton + DashboardContent wrapped in Suspense
- **Files modified:** web/src/app/dashboard/page.tsx
- **Commit:** de1154f

**2. [Rule 2 - Missing functionality] Installed shadcn checkbox component**
- **Found during:** Task 2 implementation
- **Issue:** Checkbox component was not in the 13 components installed in Plan 4-01
- **Fix:** Installed via `npx shadcn@latest add checkbox`
- **Files created:** web/src/components/ui/checkbox.tsx
- **Commit:** de1154f

## Issues Encountered

None.

## Next Phase Readiness

- Search page ready for Plan 4-03 (listing detail side panel)
  - onSelectListing handler is a console.log placeholder ready to wire
  - lastVisitedAt prop is null, ready to be populated from user session
  - ResultCard accepts isNew prop for "New" badge logic
- Filter state and result data accessible via useSearch hook for any downstream component
- URL state is fully shareable -- copy-paste URL reproduces identical search

## Self-Check: PASSED

All 10 created/modified files verified present. Both task commits (0fe9118, de1154f) verified in git log.

---
*Phase: 4*
*Completed: 2026-02-24*
