# Phase 8 Plan 1: Browser-Use Keyword Search Logic Summary

**One-liner:** Rewrite browser_scrape() with keyword search via sequential browser-use Agent runs, OR-query fallback, action history inspection for search_used detection, and 24 comprehensive tests

## Changes Made

### Task 1: Add BROWSER_SEARCH_MAX_STEPS config setting
**Commit:** 848f0f7
**Files modified:** `scraper/config.py`

- Added `BROWSER_SEARCH_MAX_STEPS` config (default 50) below existing `BROWSER_MAX_STEPS`
- Controls total step budget across all keyword search iterations per portal

### Task 2: Rewrite browser_scrape() with keyword search logic
**Commit:** 6b34e85
**Files modified:** `scraper/pipeline/browser_scraper.py`

- Added `BrowserScrapeResult` NamedTuple with `listings` and `search_used` fields
- Added `_detect_search_used(history)` helper that inspects agent action history for `input_text` action
- Added imports: `select_keyword_batch`, `deduplicate_listings` from keywords module
- No-keyword path: preserves original behavior, returns `BrowserScrapeResult(listings=..., search_used=False)`
- Keyword search path: builds keyword batches per category, navigates to portal, searches using OR queries
- OR fallback: when OR query returns 0 results and search was detected, retries with first keyword only; or_supported flag persists across categories
- Step budget enforcement: tracks total_steps against `BROWSER_SEARCH_MAX_STEPS`, breaks when exhausted
- First search prompt includes URL navigation + search form discovery (Advanced Search, hidden panels)
- Subsequent search prompts instruct agent to clear existing text and type new query
- Per-category exception handling preserves partial results from successful searches
- Deduplication applied to combined keyword search results before return
- Empty-batches edge case falls through to no-keyword behavior

### Task 3: Create comprehensive test suite
**Commit:** 75af96e
**Files created:** `scraper/tests/test_browser_scraper.py`

- 24 tests across 6 test classes, all passing
- **TestDetectSearchUsed** (4 tests): input_text detection, no input_text, None history, exception handling
- **TestBrowserScrapeResult** (2 tests): NamedTuple fields, unpacking
- **TestBrowserScrapeNoKeywords** (4 tests): search_used=False, BrowserScrapeResult type, BROWSER_MAX_STEPS, original prompt
- **TestBrowserScrapeKeywordSearch** (7 tests): first prompt with URL+keywords, Advanced Search mention, subsequent prompt with Clear, search_used=True detection, cross-category collection, dedup called, step budget
- **TestBrowserScrapeOrFallback** (3 tests): OR query used first, OR zero results falls back to single, fallback persists across categories
- **TestBrowserScrapeFallback** (4 tests): no search form returns search_used=False, returns visible listings, exception mid-search preserves results, crash resilience
- Mock approach: `sys.modules["browser_use"]` injection for lazy import, MagicMock instances for Agent/Browser/BrowserProfile/ChatOpenAI

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 compatibility for `dict[...] | None` type syntax**
- **Found during:** Task 3 (test run)
- **Issue:** `dict[str, dict[str, list[str]]] | None` union syntax in `browser_scrape()` signature requires Python 3.10+, but runtime is Python 3.9
- **Fix:** Added `from __future__ import annotations` to browser_scraper.py (matching bidsandtenders.py and orchestrator.py pattern)
- **Files modified:** `scraper/pipeline/browser_scraper.py`
- **Commit:** 75af96e (included in Task 3 commit)

**2. [Rule 1 - Bug] Mock browser_use classes must be MagicMock instances, not class references**
- **Found during:** Task 3 (test run)
- **Issue:** Setting `mod.Agent = MagicMock` (the class) instead of `MagicMock()` (an instance) prevented `.return_value` from working correctly in tests
- **Fix:** Changed all mock module attributes to MagicMock instances: `mod.Agent = MagicMock()`
- **Files modified:** `scraper/tests/test_browser_scraper.py`
- **Commit:** 75af96e

## Decisions Made

- Used `from __future__ import annotations` for Python 3.9 compat (consistent with bidsandtenders.py, orchestrator.py)
- `_detect_search_used` checks for `input_text` in action_names() -- this is the definitive signal that the agent typed into a search box
- OR fallback flag (`or_supported`) persists across categories -- once a portal shows it doesn't support OR, all subsequent categories use single keywords
- Step budget is global across all category searches, not per-category

## Metrics

- **Duration:** ~5 minutes
- **Tasks:** 3/3 completed
- **Tests:** 24 new tests (test_browser_scraper.py)
- **Files created:** 1 (test_browser_scraper.py)
- **Files modified:** 2 (config.py, browser_scraper.py)

## Self-Check: PASSED

- All 3 created/modified files exist on disk
- All 3 task commits verified in git log (848f0f7, 6b34e85, 75af96e)
- All 24 tests pass
