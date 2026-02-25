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
) -> list:
```
- In the `bidsandtenders` branch: `return await bidsandtenders_scrape(portal, keywords_by_category=keywords_by_category)`
- Other branches unchanged (canadabuys and browser don't use category keywords)

**3. Modify `process_portal()` to accept and pass `keywords_by_category`:**
```python
async def process_portal(
    conn, portal: PortalRecord, keywords=None, keywords_by_category=None, skip_embeddings: bool = False
) -> dict:
```
- Pass `keywords_by_category` to `scrape_portal()`: `raw_listings = await scrape_portal(portal, keywords_by_category=keywords_by_category)`
- Change keyword filtering to skip BidsAndTenders portals:
```python
# Step 2.5: Keyword filtering (skip for BidsAndTenders -- search box already filtered)
portal_type = classify_portal(portal)
if keywords and portal_type != "bidsandtenders":
    listing_records = filter_listings(listing_records, keywords)
```
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

Also add a test that verifies keywords_by_category is passed through:

**`test_dispatch_bidsandtenders_with_keywords`:**
- Call `scrape_portal(bidsandtenders_portal, keywords_by_category={"Cat1": {"EN": ["test"]}})`
- Assert `bidsandtenders_scrape` called with `(portal, keywords_by_category={"Cat1": {"EN": ["test"]}})`

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

**3. Add new test class `TestBidsAndTendersFilterSkip`:**

**`test_bidsandtenders_skips_keyword_filter`:**
- Mock `scrape_portal` to return a `ProcurementListing` with title "Office Furniture" (would NOT match keyword "translation")
- Mock `filter_listings` to track if called
- Call `process_portal(conn, bidsandtenders_portal, keywords=["translation"], keywords_by_category={...})`
- Assert `filter_listings` was NOT called (BidsAndTenders skips post-extraction filter)
- Assert the listing still proceeds through validation/embed/upsert

**`test_non_bidsandtenders_still_filters`:**
- Same setup but with `generic_portal` (browser type)
- Assert `filter_listings` WAS called

**`test_bidsandtenders_still_deduplicates`:**
- Mock `scrape_portal` to return listings with duplicate source_listing_ids
- Call `process_portal(conn, bidsandtenders_portal, ...)`
- Assert `deduplicate_listings` was called (dedup runs for ALL portal types)

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
**Gate:** `run_pipeline()` loads keywords by category and passes them to BidsAndTenders scraper, BidsAndTenders portals skip post-extraction keyword filtering, non-BidsAndTenders portals still apply keyword filtering, deduplication runs for all portal types, all existing tests updated and green
