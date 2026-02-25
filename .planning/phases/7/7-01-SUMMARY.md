# Phase 7 Plan 1: Keyword-by-Category Loader and BidsAndTenders Search Logic Summary

**One-liner:** Category-grouped keyword loader with random batch selection and BidsAndTenders Playwright search using OR queries with individual-keyword fallback.

## Plan Metadata

- **Phase:** 7
- **Plan:** 01
- **Type:** feature
- **Requirements:** FILT-02, FILT-04
- **Duration:** ~7 minutes
- **Completed:** 2026-02-25

## What Was Built

### Task 1: Keyword-by-Category Loader and Batch Selection
Added two functions to `scraper/pipeline/keywords.py`:

- **`load_keywords_by_category()`** -- Parses the keywords CSV and groups keywords by Category (outer) then Language (inner). Returns `dict[str, dict[str, list[str]]]`. Same validation pattern as `load_keywords()`: file exists, required columns, non-empty.
- **`select_keyword_batch()`** -- Takes one category's language dict, selects `min(per_language, available)` random keywords per language via `random.sample()`. Returns flat combined list.

Added 11 new tests in `test_keywords.py` (6 for category loader, 5 for batch selection).

### Task 2: BidsAndTenders Search Logic Rewrite
Rewrote `scraper/pipeline/bidsandtenders.py` with keyword search support:

- **`BidsAndTendersResult`** NamedTuple with `listings` and `search_used` fields
- **`_find_search_input()`** -- Tries searchbox role, "Search" placeholder, then first text input
- **`_execute_search()`** -- Fills search input, presses Enter, waits for networkidle
- **`_reset_search()`** -- Clicks Reset button or navigates back to listing URL
- **Main search loop** -- Iterates categories, builds OR queries from random batches, falls back to individual keywords when OR returns zero results, deduplicates across all categories
- **Backward compatible** -- `keywords_by_category` parameter is optional; without it, falls back to full page scrape with `search_used=False`

Created `scraper/tests/test_bidsandtenders.py` with 21 tests across 6 test classes (search input discovery, search execution, keyword search integration, search fallback, search box not found, signature/return type).

## Key Files

### Created
- `scraper/tests/test_bidsandtenders.py` -- 21 tests for BidsAndTenders scraper

### Modified
- `scraper/pipeline/keywords.py` -- Added `load_keywords_by_category()`, `select_keyword_batch()`, `import random`
- `scraper/pipeline/bidsandtenders.py` -- Rewritten with keyword search logic, `BidsAndTendersResult`, helper functions
- `scraper/tests/test_keywords.py` -- Added `TestLoadKeywordsByCategory` (6 tests), `TestSelectKeywordBatch` (5 tests)

## Commits

| Hash | Message |
|------|---------|
| b68af27 | feat(7-01): add load_keywords_by_category() and select_keyword_batch() |
| 6225e70 | feat(7-01): rewrite bidsandtenders_scrape() with keyword search logic |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python 3.9 type syntax compatibility**
- **Found during:** Task 2
- **Issue:** Plan used `dict[str, ...] | None` syntax which requires Python 3.10+. Project runs Python 3.9.6.
- **Fix:** Added `from __future__ import annotations` to `bidsandtenders.py`
- **Files modified:** `scraper/pipeline/bidsandtenders.py`
- **Commit:** 6225e70

**2. [Rule 3 - Blocking] Playwright import refactored for testability**
- **Found during:** Task 2
- **Issue:** Plan specified `_execute_search(page, query)` but noted `_execute_search` should take the search input locator directly. The inline `from playwright.async_api import async_playwright` also prevented effective mocking.
- **Fix:** Moved playwright import to module level (with try/except), changed `_execute_search` to take `(page, search_input, query)` as the important notes specified. Production code re-finds search input after each reset.
- **Files modified:** `scraper/pipeline/bidsandtenders.py`
- **Commit:** 6225e70

## Decisions Made

1. **Module-level playwright import with try/except** -- Moved from function-level to module-level for testability while preserving graceful degradation when playwright is not installed.
2. **Re-find search input after reset** -- After each `_reset_search()` call, the search input locator is re-found via `_find_search_input()` since page reloads may invalidate the previous locator reference.

## Verification

```
63 passed in 0.42s
```

All 63 tests pass (42 keyword tests + 21 bidsandtenders tests).

## Self-Check: PASSED

All 5 files verified present. Both commit hashes confirmed in git log.
