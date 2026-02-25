# Phase 7 Plan 2: Orchestrator Wiring and Test Updates Summary

**One-liner:** Wire category-grouped keywords through orchestrator to BidsAndTenders scraper, conditionally skip post-extraction filtering when search_used=True

## Changes Made

### Task 1: Wire keywords_by_category through orchestrator
**Commit:** e86bd82
**Files modified:** `scraper/pipeline/orchestrator.py`

- Added `load_keywords_by_category` to imports from keywords module
- Modified `scrape_portal()` to accept `keywords_by_category` parameter and return `(listings, search_used)` tuple instead of plain list
- BidsAndTenders branch passes `keywords_by_category` to `bidsandtenders_scrape()` and unpacks `BidsAndTendersResult`
- CanadaBuys and browser branches return `(listings, False)` since they never use search-based filtering
- Modified `process_portal()` to accept `keywords_by_category`, pass it to `scrape_portal()`, and conditionally skip `filter_listings()` when `search_used=True`
- Modified `run_pipeline()` to load both `load_keywords()` (flat) and `load_keywords_by_category()` (grouped) and pass both to `process_portal()`

### Task 2: Update orchestrator tests for new signatures and BidsAndTenders filter skip
**Commit:** ba67ede
**Files modified:** `scraper/tests/test_orchestrator.py`, `scraper/pipeline/orchestrator.py`

- Updated all `TestScrapePortal` tests for `(listings, search_used)` tuple return
- Added `test_dispatch_bidsandtenders_with_keywords` -- verifies keywords_by_category pass-through
- Added `test_scrape_portal_returns_search_used_flag` -- verifies search_used=True propagation
- Added `test_scrape_portal_non_bidsandtenders_returns_search_used_false` -- verifies non-BT portals
- Updated all `TestProcessPortal` mock return values to tuples `(listings, False)`
- Added `load_keywords_by_category` mock to all 4 `TestRunPipeline` tests
- Updated `test_run_pipeline_single_portal` assertion to include `keywords_by_category` param
- Added new `TestSearchUsedFilterLogic` class with 4 tests:
  - `test_search_used_true_skips_keyword_filter` -- filter NOT called when search box was used
  - `test_search_used_false_applies_keyword_filter` -- filter IS called when search box not found
  - `test_non_bidsandtenders_still_filters` -- non-BT portals always filter
  - `test_all_portals_still_deduplicate` -- dedup runs regardless of search_used

### Task 3: Full test suite verification
- All 85 phase-7 tests pass (bidsandtenders: 21, keywords: 42, orchestrator: 22)
- All 160 scraper tests pass
- Pre-existing API benchmark test failure (connection refused -- requires running server) unrelated to changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 compatibility for `dict | None` type syntax**
- **Found during:** Task 2 (test run)
- **Issue:** `dict | None` union type syntax in `scrape_portal()` signature requires Python 3.10+, but runtime is Python 3.9
- **Fix:** Added `from __future__ import annotations` to orchestrator.py (matching bidsandtenders.py pattern)
- **Files modified:** `scraper/pipeline/orchestrator.py`
- **Commit:** ba67ede (included in Task 2 commit)

## Decisions Made

- Used `from __future__ import annotations` for Python 3.9 compatibility (consistent with bidsandtenders.py)
- search_used flag approach cleanly separates "search was performed" from "portal type", handling the fallback case where BidsAndTenders search box is not found

## Metrics

- **Duration:** ~4 minutes
- **Tasks:** 3/3 completed
- **Tests:** 22 orchestrator tests (was 16, added 6 new)
- **Files modified:** 2 (orchestrator.py, test_orchestrator.py)
