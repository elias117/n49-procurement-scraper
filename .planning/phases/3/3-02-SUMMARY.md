---
phase: 3
plan: 02
subsystem: api
tags: [fastapi, pgvector, tsvector, rrf, hybrid-search, psycopg2, openai-embeddings]

# Dependency graph
requires:
  - phase: 3-01
    provides: FastAPI scaffold, DB connection, Pydantic models, search stub, test infrastructure
provides:
  - Dynamic SQL filter builder (6 dimensions)
  - Query embedding helper (OpenAI text-embedding-3-small)
  - Hybrid search engine (keyword + semantic + RRF merge)
  - Wired /search endpoint with full parameter handling
affects: [3-03, 3-04, 4]

# Tech tracking
tech-stack:
  added: [openai, tenacity]
  patterns: [CTE-based hybrid SQL, RRF scoring, parameterized filter construction]

key-files:
  created:
    - api/search/query_builder.py
    - api/search/embeddings.py
    - api/search/hybrid.py
    - api/tests/test_search.py
  modified:
    - api/routers/search.py
    - api/tests/test_query_builder.py
    - api/tests/test_hybrid.py

key-decisions:
  - "Python 3.9 compat: Optional[X] instead of X | None union syntax"
  - "Browse mode (empty query) falls back to posting_date DESC sort"
  - "Three SQL paths: browse (no CTEs), keyword-only (tsvector only), full hybrid (RRF)"

patterns-established:
  - "Filter builder returns (clause_str, params_dict) tuple for reuse across search and facets"
  - "Sort clause builder maps logical names to SQL columns with NULLS LAST"
  - "Embedding failure is non-fatal: graceful fallback to keyword-only search"

requirements-completed: [SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08, SRCH-09, SRCH-10]

# Metrics
duration: 5min
completed: 2026-02-24
---

# Phase 3 Plan 02: Core Hybrid Search Engine Summary

**Hybrid keyword + semantic search with RRF merge, 6-dimension filter builder, and graceful embedding fallback wired into GET /search**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T00:57:26Z
- **Completed:** 2026-02-25T01:02:36Z
- **Tasks:** 7
- **Files modified:** 7

## Accomplishments
- Dynamic SQL filter builder supporting all 6 filter dimensions with correct NULL handling per user decisions
- Query embedding helper with OpenAI retry and lazy client initialization
- Full CTE-based hybrid search with Reciprocal Rank Fusion, keyword-only fallback, and browse mode
- Wired /search endpoint replacing stub with complete parameter handling and graceful degradation
- 29 total tests passing across the API test suite (13 filter, 6 hybrid, 7 endpoint, 2 health, 1 facet placeholder)

## Task Commits

Each task was committed atomically:

1. **Task 1.1: Implement dynamic SQL filter builder** - `e6bb08a` (feat)
2. **Task 1.2: Write comprehensive filter builder tests** - `637b39d` (test)
3. **Task 1.3: Create query embedding helper** - `e6f7519` (feat)
4. **Task 2.1: Implement hybrid search query execution** - `0523dbf` (feat)
5. **Task 2.2: Write hybrid search and RRF tests** - `584fd01` (test)
6. **Task 2.3: Wire search endpoint with full parameter handling** - `b838f53` (feat)
7. **Task 2.4: Create search endpoint integration tests** - `c4fab3a` (test)

## Files Created/Modified
- `api/search/query_builder.py` - Dynamic WHERE clause + ORDER BY construction from SearchRequest
- `api/search/embeddings.py` - OpenAI embedding helper with 3x retry and lazy client
- `api/search/hybrid.py` - CTE-based hybrid search with RRF, keyword-only, and browse modes
- `api/routers/search.py` - Full GET /search endpoint replacing stub
- `api/tests/test_query_builder.py` - 13 tests covering all filter dimensions and sort options
- `api/tests/test_hybrid.py` - 6 tests for SQL structure, oversample, offset, RRF k
- `api/tests/test_search.py` - 7 integration tests for endpoint behavior

## Decisions Made
- Python 3.9 compatibility: used `Optional[X]` with `from __future__ import annotations` instead of `X | None` union syntax (dev machine runs 3.9, Docker runs 3.11+)
- Browse mode (empty query) falls back to `posting_date DESC` sort since relevance scoring requires a query
- Three separate SQL builder functions for clarity: browse, keyword-only, and full hybrid -- avoids complex conditional SQL string assembly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python 3.9 type hint compatibility**
- **Found during:** Task 1.3 (Create query embedding helper)
- **Issue:** `OpenAI | None` union syntax not supported in Python 3.9 (requires 3.10+)
- **Fix:** Changed to `Optional[OpenAI]` with `from __future__ import annotations`
- **Files modified:** `api/search/embeddings.py`
- **Verification:** Import succeeds on Python 3.9
- **Committed in:** e6f7519 (Task 1.3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for dev environment compatibility. No scope creep.

## Issues Encountered
None beyond the Python 3.9 type hint fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Search engine is fully functional pending facet counts and keyword highlights (Plan 3-03)
- Filter clause builder returns reusable (clause, params) tuple ready for facet count queries
- Exact match mode ready but needs dedicated SQL path (Plan 3-03)
- All 29 tests pass, providing regression safety for Plan 3-03 changes

## Self-Check: PASSED

- All 7 created/modified files verified on disk
- All 7 task commit hashes verified in git log

---
*Phase: 3*
*Plan: 02*
*Completed: 2026-02-24*
