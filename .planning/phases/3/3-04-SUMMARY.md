---
phase: 3
plan: 04
subsystem: api, testing
tags: [benchmark, integration-test, httpx, pytest, search-validation, hybrid-search]

# Dependency graph
requires:
  - phase: 3-03
    provides: Complete search API with facets, highlights, exact match, 43 unit tests
provides:
  - 20-query benchmark validating all search requirements against live data
  - Schema migration 004 applied (search_vector stored column, original_closing_date)
  - End-to-end proof that API + DB integration works correctly
affects: [phase-4-dashboard, deployment]

# Tech tracking
tech-stack:
  added: [httpx (test client)]
  patterns: [live-database integration testing with pytest skip markers]

key-files:
  created:
    - api/tests/test_benchmark.py
  modified:
    - db/migrations/004_search_layer.sql (applied to running DB)

key-decisions:
  - "Benchmark tests run against live API via httpx, not via TestClient, to validate full HTTP stack"
  - "Tests skip automatically when DATABASE_URL not set (CI-safe)"

patterns-established:
  - "Integration test pattern: pytest.mark.skipif on DATABASE_URL for live-DB-only tests"

requirements-completed: [SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, SRCH-09, SRCH-10]

# Metrics
duration: 3min
completed: 2026-02-24
---

# Phase 3 Plan 04: Integration Validation and 20-Query Benchmark Summary

**20-query benchmark validates all 10 search requirements against 897 live CanadaBuys listings -- keyword, semantic, hybrid RRF, 7 filter dimensions, sort, exact match, combined filters**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T01:15:46Z
- **Completed:** 2026-02-25T01:18:43Z
- **Tasks:** 4 (2 runtime operational, 1 code, 1 execution)
- **Files modified:** 1

## Accomplishments
- Schema migration 004 applied to running PostgreSQL (stored tsvector column + original_closing_date)
- API service built and started via Docker Compose -- health check confirms 897 listings
- 20 benchmark queries all pass in 5.36s covering every SRCH requirement
- 43 existing unit tests still pass (zero regressions)
- Semantic search correctly surfaces "construction" results from "construction contracts expiring soon" query
- Exact match finds 32 PW-prefixed tender numbers
- Province filter correctly limits to Ontario (+ National/NULL)

## Task Commits

Each task was committed atomically:

1. **Task 1.1: Apply schema migration** - (runtime operation, no file changes -- migration file from 3-01)
2. **Task 1.2: Build and start API** - (runtime operation, no file changes -- Dockerfile/compose from 3-01)
3. **Task 2.1: Create 20-query benchmark test** - `a1e2e23` (test)
4. **Task 2.2: Run benchmark and document results** - (execution task, results documented here)

## Files Created/Modified
- `api/tests/test_benchmark.py` - 20 integration tests validating all search requirements against live data

## Benchmark Results

```
20 passed in 5.36s

Test 01: IT consulting keyword search -- 158 results PASS
Test 02: construction keyword -- PASS
Test 03: janitorial services keyword -- PASS
Test 04: natural language (office equipment) -- PASS
Test 05: conceptual (technology modernization) -- PASS
Test 06: hybrid RRF (professional services) -- PASS
Test 07: short query (audit) -- PASS
Test 08: default open-only -- PASS
Test 09: include_closed -- PASS
Test 10: Ontario province filter -- PASS
Test 11: portal filter -- PASS
Test 12: posting date range -- PASS
Test 13: classification code -- PASS
Test 14: value range filter -- PASS
Test 15: value filter excludes nulls -- PASS
Test 16: sort by posting_date desc -- PASS
Test 17: sort by closing_date asc -- PASS
Test 18: sort by value desc -- PASS
Test 19: exact match PW- tender -- 32 results PASS
Test 20: combined filters + pagination + facets -- PASS
```

## Decisions Made
- Benchmark tests use httpx.Client against the live API (not FastAPI TestClient) to validate the full HTTP path including uvicorn
- Tests annotated with `pytest.mark.skipif` on DATABASE_URL so they are safely skipped in CI without database access

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None -- all 20 tests passed on first run.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete search API validated end-to-end with 63 total tests (43 unit + 20 benchmark)
- All SRCH-01 through SRCH-10 requirements covered
- API ready for Phase 4 dashboard to consume via GET /search and GET /health endpoints
- Docker Compose services (db + api) running and healthy

---
*Phase: 3*
*Completed: 2026-02-24*
