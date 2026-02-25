---
phase: 3
plan: 03
subsystem: api
tags: [facets, highlights, ts_headline, bleach, xss, ilike, exact-match, pagination]

# Dependency graph
requires:
  - phase: 3-02
    provides: hybrid search engine, filter builder, search endpoint wiring
provides:
  - facet count queries (province + portal breakdowns)
  - XSS-safe keyword highlighting via ts_headline + bleach
  - exact match mode with ILIKE search for tender numbers
  - production-ready search responses with snippets and facets
affects: [phase-4-frontend, phase-5-deployment]

# Tech tracking
tech-stack:
  added: [bleach]
  patterns: [ts_headline sanitization, CTE facet aggregation, ILIKE exact match with rank ordering]

key-files:
  created:
    - api/search/facets.py
    - api/search/highlights.py
    - api/tests/test_facets.py
    - api/tests/test_highlights.py
    - api/tests/test_exact_match.py
  modified:
    - api/search/hybrid.py
    - api/routers/search.py
    - api/tests/test_search.py

key-decisions:
  - "bleach.clean with strip=True for XSS-safe ts_headline output -- strips all HTML except <mark> tags"
  - "ts_headline applied AFTER pagination (on final result set only) to avoid performance pitfall"
  - "Browse mode uses LEFT(COALESCE(description, title), 200) instead of ts_headline since no query exists"
  - "Exact match uses ILIKE with CASE-based ranking: title=0, source_listing_id=1, description=2"

patterns-established:
  - "Snippet sanitization: all ts_headline output goes through sanitize_snippet() before response"
  - "Facet queries reuse same filter_clause as search for consistency"
  - "Exact match dispatched at router level before hybrid search"

requirements-completed: [SRCH-01, SRCH-08, SRCH-10]

# Metrics
duration: 6min
completed: 2026-02-24
---

# Phase 3, Plan 03: Search UX Features Summary

**Facet counts, ts_headline keyword highlights with XSS sanitization, ILIKE exact match mode, and pagination total_count wired into production search response**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-25T01:05:48Z
- **Completed:** 2026-02-25T01:12:07Z
- **Tasks:** 6
- **Files modified:** 8

## Accomplishments
- Province and portal facet counts returned alongside search results via single CTE query
- XSS-safe keyword highlighting using ts_headline with bleach sanitization (strips all HTML except <mark>)
- Exact match mode for tender number lookup using ILIKE with ranked results (title > listing ID > description)
- Search response now production-ready: facets, highlighted snippets, total_count for pagination all working
- Test count increased from 29 to 43 (14 new tests across 3 test files)

## Task Commits

Each task was committed atomically:

1. **Task 1.1: Implement facet count queries** - `57d6ecf` (feat)
2. **Task 1.2: Write facet count tests** - `ff8af6f` (test)
3. **Task 1.3: Implement keyword highlight sanitization** - `d14e7a8` (feat)
4. **Task 1.4: Write highlight sanitization tests** - `903313c` (test)
5. **Task 2.1: Add ts_headline + wire facets** - `b5a0fad` (feat)
6. **Task 2.2: Implement exact match mode** - `2c76fc9` (feat)
7. **Task 2.3: Write exact match tests** - `713c952` (test)

## Files Created/Modified
- `api/search/facets.py` - Facet count CTE query returning province/portal breakdowns
- `api/search/highlights.py` - sanitize_snippet() and TS_HEADLINE_OPTIONS constant
- `api/search/hybrid.py` - Added ts_headline to all SQL paths, execute_exact_search()
- `api/routers/search.py` - Wired facets and exact match dispatch into endpoint
- `api/tests/test_facets.py` - 5 tests for facet count queries
- `api/tests/test_highlights.py` - 5 tests for XSS sanitization
- `api/tests/test_exact_match.py` - 5 tests for ILIKE exact match
- `api/tests/test_search.py` - Updated exact mode mock to use execute_exact_search

## Decisions Made
- bleach.clean with strip=True for XSS-safe ts_headline output -- strips tags but preserves text content, which is safe since JS cannot execute without script tags
- ts_headline applied AFTER pagination on the final result set only, avoiding the performance pitfall of running it on all candidates
- Browse mode (empty query) uses LEFT(COALESCE(description, title), 200) for snippets since ts_headline requires a query
- Exact match uses ILIKE with phraseto_tsquery for highlighting and CASE-based ranking to prioritize title matches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed bleach dependency locally**
- **Found during:** Task 1.3 (highlights module)
- **Issue:** bleach was in requirements.txt but not installed in local dev environment
- **Fix:** pip3 install bleach (already declared in requirements.txt, just missing locally)
- **Files modified:** None (requirements.txt already had it)
- **Verification:** Import succeeds after install

**2. [Rule 1 - Bug] Fixed highlight test assertion for bleach behavior**
- **Found during:** Task 1.4 (highlight tests)
- **Issue:** Test asserted "alert" text should be removed, but bleach with strip=True correctly preserves text content while removing script tags
- **Fix:** Updated assertion to check tags are stripped (not text content), which is the correct security behavior
- **Files modified:** api/tests/test_highlights.py
- **Verification:** All 5 highlight tests pass

**3. [Rule 1 - Bug] Updated existing exact mode test mock target**
- **Found during:** Task 2.2 (exact match implementation)
- **Issue:** Existing test_search_exact_mode_skips_embedding mocked execute_hybrid_search but router now dispatches to execute_exact_search for mode=exact
- **Fix:** Changed mock target from execute_hybrid_search to execute_exact_search
- **Files modified:** api/tests/test_search.py
- **Verification:** All 43 tests pass

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Search API now returns production-ready responses with facets, highlights, and both search modes
- Plan 3-04 (API hardening: rate limiting, error handling, CORS) is ready to execute
- All 43 tests passing, covering facets, highlights, exact match, hybrid search, query builder, and endpoint integration

## Self-Check: PASSED

All 9 files verified present. All 7 task commits verified in git log.

---
*Phase: 3*
*Completed: 2026-02-24*
