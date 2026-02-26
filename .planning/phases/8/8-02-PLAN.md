# Phase 8 Plan 2 — Orchestrator Wiring and Test Updates

**Phase Goal:** Generic browser-use portals search for keywords using portal search forms instead of scraping all visible listings.
**Plan Goal:** Wire `keywords_by_category` through the orchestrator to `browser_scrape()`, unpack `BrowserScrapeResult` in the browser dispatch branch, and update all affected orchestrator tests.
**Requirements:** FILT-03, FILT-04
**Depends on:** 8-01 (browser keyword search logic + BrowserScrapeResult must exist)

## Context

After Plan 8-01, `browser_scrape()` accepts an optional `keywords_by_category` parameter and returns `BrowserScrapeResult(listings, search_used)` instead of a bare list. The orchestrator must now:

1. Pass `keywords_by_category` through `scrape_portal()` to `browser_scrape()` for generic portals
2. Unpack `BrowserScrapeResult` the same way it unpacks `BidsAndTendersResult`
3. The existing `search_used` filter logic already handles this correctly — when `search_used=True`, keyword filtering is skipped; when `search_used=False`, it's applied

Current orchestrator browser branch (lines 80-82 of `scraper/pipeline/orchestrator.py`):
```python
else:
    listings = await browser_scrape(portal)
    return listings, False
```

New browser branch:
```python
else:
    result = await browser_scrape(portal, keywords_by_category=keywords_by_category)
    return result.listings, result.search_used
```

The rest of the orchestrator (keyword filtering, deduplication, validation, embedding, upsert) already works correctly with the `search_used` flag from Phase 7. No other orchestrator changes needed.

Key files:
- `scraper/pipeline/orchestrator.py` — one-line change in `scrape_portal()`
- `scraper/tests/test_orchestrator.py` — test updates
- `scraper/pipeline/browser_scraper.py` — already returns `BrowserScrapeResult` from Plan 8-01

## Tasks

### Task 1: Wire keywords_by_category to browser_scrape in orchestrator
**File:** `scraper/pipeline/orchestrator.py`
**Action:** MODIFY

**1. Add import:**
```python
from scraper.pipeline.browser_scraper import browser_scrape, BrowserScrapeResult
```
(Replace the existing `from scraper.pipeline.browser_scraper import browser_scrape`)

**2. Update the browser branch in `scrape_portal()` (lines 80-82):**

Change from:
```python
else:
    listings = await browser_scrape(portal)
    return listings, False
```

To:
```python
else:
    result = await browser_scrape(
        portal, keywords_by_category=keywords_by_category
    )
    return result.listings, result.search_used
```

That's the only code change. The existing `process_portal()` already:
- Passes `keywords_by_category` to `scrape_portal()` (line 110)
- Skips `filter_listings()` when `search_used=True` (line 134)
- Runs `deduplicate_listings()` always (line 138)

### Task 2: Update orchestrator tests for browser_scrape changes
**File:** `scraper/tests/test_orchestrator.py`
**Action:** MODIFY

**1. Update imports:**
```python
from scraper.pipeline.browser_scraper import BrowserScrapeResult
```

**2. Update `TestScrapePortal.test_dispatch_browser`:**

The mock return value must change from a bare list to a `BrowserScrapeResult`:
```python
mock_scrape.return_value = BrowserScrapeResult(listings=[], search_used=False)
```

And the assertion must include `keywords_by_category`:
```python
mock_scrape.assert_called_once_with(
    generic_portal, keywords_by_category=None
)
```

**3. Update `TestScrapePortal.test_scrape_portal_non_bidsandtenders_returns_search_used_false`:**

Same changes — mock return value becomes `BrowserScrapeResult`:
```python
mock_scrape.return_value = BrowserScrapeResult(
    listings=[mock_listing], search_used=False
)
```

And assertion:
```python
mock_scrape.assert_called_once_with(
    generic_portal, keywords_by_category=None
)
```

**4. Add new test `test_dispatch_browser_with_keywords`:**

```python
@patch(
    "scraper.pipeline.orchestrator.browser_scrape",
    new_callable=AsyncMock,
)
def test_dispatch_browser_with_keywords(self, mock_scrape, generic_portal):
    """Browser portals pass keywords_by_category through to browser_scrape."""
    kw_by_cat = {"Cat1": {"EN": ["translation"]}}
    mock_scrape.return_value = BrowserScrapeResult(listings=[], search_used=True)

    listings, search_used = asyncio.get_event_loop().run_until_complete(
        scrape_portal(generic_portal, keywords_by_category=kw_by_cat)
    )

    mock_scrape.assert_called_once_with(
        generic_portal, keywords_by_category=kw_by_cat
    )
    assert search_used is True
```

**5. Add new test `test_browser_search_used_true_skips_filter`:**

In `TestSearchUsedFilterLogic`, add a test that proves browser portals with `search_used=True` skip keyword filtering:

```python
def test_browser_search_used_true_skips_keyword_filter(
    self, ..., mock_conn, generic_portal,
):
    """When browser search_used=True, keyword filter is NOT called."""
    mock_start.return_value = "run-id"
    test_listing = ListingRecord(
        title="Translation Services",
        source_portal="portal-gen-001",
        source_listing_id="GEN-001",
        language="en",
    )
    mock_scrape.return_value = ([test_listing], True)  # search_used=True
    mock_dedup.return_value = [test_listing]
    mock_validate.return_value = test_listing
    mock_embed.return_value = [test_listing]
    mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

    asyncio.get_event_loop().run_until_complete(
        process_portal(
            mock_conn, generic_portal,
            keywords=["translation"],
            keywords_by_category={"Cat": {"EN": ["translation"]}},
        )
    )

    mock_filter.assert_not_called()
```

**6. Add new test `test_browser_search_used_false_applies_filter`:**

Proves that browser portals with `search_used=False` (no search form found) still get keyword filtering:

```python
def test_browser_search_used_false_applies_keyword_filter(
    self, ..., mock_conn, generic_portal,
):
    """When browser search_used=False, keyword filter IS applied."""
    mock_start.return_value = "run-id"
    test_listing = ListingRecord(
        title="Translation Services",
        source_portal="portal-gen-001",
        source_listing_id="GEN-001",
        language="en",
    )
    mock_scrape.return_value = ([test_listing], False)
    mock_filter.return_value = [test_listing]
    mock_dedup.return_value = [test_listing]
    mock_validate.return_value = test_listing
    mock_embed.return_value = [test_listing]
    mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

    asyncio.get_event_loop().run_until_complete(
        process_portal(
            mock_conn, generic_portal,
            keywords=["translation"],
            keywords_by_category={"Cat": {"EN": ["translation"]}},
        )
    )

    mock_filter.assert_called_once()
```

### Task 3: Update ROADMAP.md with plan entries
**File:** `.planning/ROADMAP.md`
**Action:** MODIFY

Add plan entries under Phase 8:
```
**Plans:** 2 plans
Plans:
- [ ] 8-01-PLAN.md — Browser-use keyword search: agent prompt, OR fallback, action history detection + tests
- [ ] 8-02-PLAN.md — Orchestrator wiring: pass keywords to browser_scrape, unpack BrowserScrapeResult + test updates
```

### Task 4: Full test suite verification
**Files:** (no file changes — verification only)
**Action:** VERIFY

Run the complete test suite:
```bash
cd /Users/clawbot/dev && python -m pytest -x -q
```

All existing tests must still pass. The key risk is `test_orchestrator.py` tests breaking due to `browser_scrape` now being called with `keywords_by_category` and returning `BrowserScrapeResult` instead of a bare list. Task 2 handles those updates.

Also verify the specific Phase 8 tests:
```bash
cd /Users/clawbot/dev && python -m pytest scraper/tests/test_browser_scraper.py scraper/tests/test_orchestrator.py -x -v
```

## Verification

**Command:** `cd /Users/clawbot/dev && python -m pytest -x -q`
**Expected:** All tests pass (full suite)
**Gate:** `scrape_portal()` passes `keywords_by_category` to `browser_scrape()` for generic portals; `BrowserScrapeResult.search_used` correctly drives conditional keyword filtering (True=skip, False=apply); existing BidsAndTenders and CanadaBuys behavior unaffected; all orchestrator tests updated and green; ROADMAP.md updated with plan entries
