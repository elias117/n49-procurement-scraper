# Phase 7 Plan 2 — Orchestrator Wiring and Test Updates

**Phase Goal:** All ~29 BidsAndTenders portals use the portal's search interface to query keywords via Playwright, returning only relevant listings.
**Plan Goal:** Wire category-grouped keywords through the orchestrator to `bidsandtenders_scrape()`, skip post-extraction keyword filtering for BidsAndTenders portals, and update all existing orchestrator tests for the new function signatures and behavior.
**Requirements:** FILT-02, FILT-04
**Depends on:** 7-01 (keywords by category + bidsandtenders search logic must exist)

## Context

After Plan 1, `bidsandtenders_scrape()` accepts an optional `keywords_by_category` parameter and performs keyword searches when provided. The orchestrator must now:

1. Load keywords by category (in addition to the flat list) at pipeline startup
2. Pass `keywords_by_category` through `scrape_portal()` to `bidsandtenders_scrape()`
3. Skip post-extraction `filter_listings()` for BidsAndTenders portals (search box already filtered)
4. Keep deduplication for all portal types

Current orchestrator flow (from `scraper/pipeline/orchestrator.py`):
- `run_pipeline()` calls `load_keywords()` -> flat list
- `process_portal()` calls `scrape_portal()` -> raw listings
- `process_portal()` applies `filter_listings()` if keywords present
- `process_portal()` applies `deduplicate_listings()` always

New flow:
- `run_pipeline()` calls BOTH `load_keywords()` (flat) AND `load_keywords_by_category()` (grouped)
- `process_portal()` receives `keywords_by_category` and passes to `scrape_portal()`
- `scrape_portal()` passes `keywords_by_category` to `bidsandtenders_scrape()` for BidsAndTenders portals
- `process_portal()` skips `filter_listings()` for BidsAndTenders portals (uses `classify_portal()` to check)
- Deduplication still runs for all portal types

Key files:
- `scraper/pipeline/orchestrator.py` — main changes
- `scraper/tests/test_orchestrator.py` — test updates
- `scraper/pipeline/keywords.py` — import `load_keywords_by_category`
- `scraper/pipeline/bidsandtenders.py` — already accepts `keywords_by_category` from Plan 1

## Tasks

### Task 1: Wire keywords_by_category through orchestrator
**File:** `scraper/pipeline/orchestrator.py`
**Action:** MODIFY

**1. Add import:**
```python
from scraper.pipeline.keywords import load_keywords, load_keywords_by_category, filter_listings, deduplicate_listings
```

**2. Modify `scrape_portal()` to accept and pass `keywords_by_category`:**
```python
async def scrape_portal(
    portal: PortalRecord,
    keywords_by_category: dict | None = None,
) -> tuple[list, bool]:
```
- Return type is now `(listings, search_used)` — `search_used` is True when keyword search was actually performed (BidsAndTenders only)
- In the `bidsandtenders` branch: `result = await bidsandtenders_scrape(portal, keywords_by_category=keywords_by_category); return result.listings, result.search_used`
- Other branches: `return listings, False` (non-BidsAndTenders portals never use search-based filtering)
- Import `BidsAndTendersResult` from `bidsandtenders.py` if needed for type hints

**3. Modify `process_portal()` to accept and pass `keywords_by_category`:**
```python
async def process_portal(
    conn, portal: PortalRecord, keywords=None, keywords_by_category=None, skip_embeddings: bool = False
) -> dict:
```
- Pass `keywords_by_category` to `scrape_portal()`: `raw_listings, search_used = await scrape_portal(portal, keywords_by_category=keywords_by_category)`
- Change keyword filtering to conditionally skip based on `search_used` flag:
```python
# Step 2.5: Keyword filtering
# Skip ONLY if keyword search was actually performed (search_used=True).
# If search box was not found (search_used=False), apply post-extraction filter
# per CONTEXT.md: "Search box not found: fall back to current behavior, apply keyword filter"
if keywords and not search_used:
    listing_records = filter_listings(listing_records, keywords)
```
- This correctly handles the fallback case: when a BidsAndTenders portal's search box is not found, `search_used=False` is returned, and keyword filtering is applied
- Deduplication remains unchanged (runs for all portal types)

**4. Modify `run_pipeline()` to load both keyword formats:**
```python
keywords = load_keywords()
keywords_by_category = load_keywords_by_category()
```
- Pass both to `process_portal()`:
```python
stats = await process_portal(
    conn, portal,
    keywords=keywords,
    keywords_by_category=keywords_by_category,
    skip_embeddings=skip_embeddings,
)
```

### Task 2: Update orchestrator tests for new signatures and BidsAndTenders filter skip
**File:** `scraper/tests/test_orchestrator.py`
**Action:** MODIFY

**1. Update `TestScrapePortal.test_dispatch_bidsandtenders`:**

The mock assertion must change from:
```python
mock_scrape.assert_called_once_with(bidsandtenders_portal)
```
To:
```python
mock_scrape.assert_called_once_with(bidsandtenders_portal, keywords_by_category=None)
```
(Because `scrape_portal()` now passes `keywords_by_category` to `bidsandtenders_scrape()`.)

Also update the mock return value to return a `BidsAndTendersResult`:
```python
from scraper.pipeline.bidsandtenders import BidsAndTendersResult
mock_scrape.return_value = BidsAndTendersResult(listings=[], search_used=False)
```

And update all callers of `scrape_portal()` to unpack the tuple return: `listings, search_used = await scrape_portal(...)`

Also add tests that verify keywords_by_category pass-through and search_used flag:

**`test_dispatch_bidsandtenders_with_keywords`:**
- Call `scrape_portal(bidsandtenders_portal, keywords_by_category={"Cat1": {"EN": ["test"]}})`
- Assert `bidsandtenders_scrape` called with `(portal, keywords_by_category={"Cat1": {"EN": ["test"]}})`

**`test_scrape_portal_returns_search_used_flag`:**
- Mock `bidsandtenders_scrape` to return `BidsAndTendersResult(listings=[...], search_used=True)`
- Call `scrape_portal(bidsandtenders_portal, keywords_by_category={...})`
- Assert return is `([...], True)`

**`test_scrape_portal_non_bidsandtenders_returns_search_used_false`:**
- Call `scrape_portal(generic_portal)` for a non-BidsAndTenders portal
- Assert return is `(listings, False)`

**2. Update `TestRunPipeline` tests:**

All `run_pipeline` tests currently mock `load_keywords`. They must now also mock `load_keywords_by_category`:

```python
@patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
@patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
```

Update `test_run_pipeline_single_portal` assertion:
```python
mock_process.assert_called_once_with(
    mock_conn, portal, keywords=["test"],
    keywords_by_category={"Cat": {"EN": ["test"]}},
    skip_embeddings=False,
)
```

**3. Add new test class `TestSearchUsedFilterLogic`:**

**`test_search_used_true_skips_keyword_filter`:**
- Mock `scrape_portal` to return `(listings, search_used=True)` — simulates BidsAndTenders with working search box
- Mock `filter_listings` to track if called
- Call `process_portal(conn, bidsandtenders_portal, keywords=["translation"], keywords_by_category={...})`
- Assert `filter_listings` was NOT called (search was used, no post-filtering needed)

**`test_search_used_false_applies_keyword_filter`:**
- Mock `scrape_portal` to return `(listings, search_used=False)` — simulates BidsAndTenders where search box was NOT found (fallback)
- Mock `filter_listings` to track if called
- Call `process_portal(conn, bidsandtenders_portal, keywords=["translation"], keywords_by_category={...})`
- Assert `filter_listings` WAS called (CONTEXT.md: search box not found = apply keyword filter)

**`test_non_bidsandtenders_still_filters`:**
- Mock `scrape_portal` to return `(listings, search_used=False)` — non-BidsAndTenders portals never use search
- Call `process_portal(conn, generic_portal, keywords=["translation"])`
- Assert `filter_listings` WAS called

**`test_all_portals_still_deduplicate`:**
- Mock `scrape_portal` to return listings with duplicate source_listing_ids (both search_used=True and False cases)
- Call `process_portal(conn, bidsandtenders_portal, ...)`
- Assert `deduplicate_listings` was called (dedup runs for ALL portal types regardless of search_used)

### Task 3: Full test suite verification
**Files:** (no file changes — verification only)
**Action:** VERIFY

Run the complete test suite to ensure nothing is broken:
```bash
cd /Users/clawbot/dev && python -m pytest -x -q
```

All existing tests must still pass. The key risk is `test_orchestrator.py` tests breaking due to the signature changes in `scrape_portal()` and `process_portal()`. Task 2 handles those updates.

Also verify the specific phase 7 tests:
```bash
cd /Users/clawbot/dev && python -m pytest scraper/tests/test_bidsandtenders.py scraper/tests/test_keywords.py scraper/tests/test_orchestrator.py -x -v
```

## Verification
**Command:** `cd /Users/clawbot/dev && python -m pytest -x -q`
**Expected:** All tests pass (full suite including updated orchestrator tests, new bidsandtenders tests, keyword tests)
**Gate:** `run_pipeline()` loads keywords by category and passes them to BidsAndTenders scraper, keyword filtering is skipped ONLY when `search_used=True` (search box found and used), keyword filtering is applied when `search_used=False` (search box not found fallback, or non-BidsAndTenders portals), deduplication runs for all portal types, all existing tests updated and green
