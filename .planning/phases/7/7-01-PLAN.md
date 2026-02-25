# Phase 7 Plan 1 — Keyword-by-Category Loader and BidsAndTenders Search Logic

**Phase Goal:** All ~29 BidsAndTenders portals use the portal's search interface to query keywords via Playwright, returning only relevant listings.
**Plan Goal:** Add `load_keywords_by_category()` and `select_keyword_batch()` to `keywords.py`, then rewrite `bidsandtenders_scrape()` to perform keyword searches via the portal search box with OR-query support and fallback. Create `test_bidsandtenders.py` with full test coverage.
**Requirements:** FILT-02, FILT-04
**Depends on:** Phase 6 complete (keyword module + dedup exist)

## Context

The current `bidsandtenders_scrape()` (123 lines in `scraper/pipeline/bidsandtenders.py`) navigates to `{base_url}/Module/Tenders/en` and scrapes ALL visible listings via LLM extraction. Phase 7 changes this to: for each keyword category, build an OR query from a random 5-EN + 5-FR keyword batch, type it into the search box, extract results, aggregate across all categories, and deduplicate before returning.

The existing `keywords.py` returns a flat `list[str]` via `load_keywords()`. We need a new `load_keywords_by_category()` that returns `dict[str, dict[str, list[str]]]` (category -> language -> keywords) for per-category batch selection.

Key locked decisions from user:
- 5 random keywords per language per batch (up to 10 terms per search)
- OR-joined queries: `translation OR traduction OR interpreter OR linguist`
- Zero results from OR query triggers individual-keyword fallback
- Fallback scope is per-portal (if first category OR fails, skip OR for remaining categories)
- Search box not found = fall back to scraping all visible listings (original behavior)
- No post-extraction keyword filtering for BidsAndTenders (search box is sufficient)
- Iterate dynamically over CSV categories (currently 5, not hardcoded)

Key files to reference:
- `scraper/pipeline/keywords.py` — existing keyword module to extend
- `scraper/pipeline/bidsandtenders.py` — scraper to rewrite
- `scraper/pipeline/extraction.py` — `extract_listings_from_html()` used for HTML -> listings
- `scraper/models.py` — `ProcurementListing` return type
- `keywords_library.csv` — 5 categories, 120 keywords, EN+FR

## Tasks

### Task 1: Add `load_keywords_by_category()` and `select_keyword_batch()` to keywords.py
**Files:** `scraper/pipeline/keywords.py`, `scraper/tests/test_keywords.py`
**Action:** MODIFY

Add two new functions to `scraper/pipeline/keywords.py`:

**1. `load_keywords_by_category(csv_path=KEYWORDS_CSV_PATH) -> dict[str, dict[str, list[str]]]`**
- Parse the CSV (same validation as `load_keywords()`: file exists, required columns, non-empty)
- Group keywords by Category (outer key) then Language (inner key: "EN" or "FR")
- Lowercase all keywords
- Return structure like: `{"Core Language and Translation": {"EN": ["translation", ...], "FR": ["traduction", ...]}, ...}`
- Log: `"Loaded %d keywords across %d categories"` with total count and category count
- Raise `SystemExit` on missing file, missing columns, or empty result (same pattern as `load_keywords()`)

**2. `select_keyword_batch(category_keywords: dict[str, list[str]], per_language: int = 5) -> list[str]`**
- Takes one category's language dict (e.g., `{"EN": [...], "FR": [...]}`)
- For each language ("EN", "FR"), select `min(per_language, len(available))` random keywords using `random.sample()`
- Return combined flat list of selected keywords
- Import `random` at top of file

Add tests to `scraper/tests/test_keywords.py`:

**Class `TestLoadKeywordsByCategory`:**
- `test_loads_from_real_csv` — loads real CSV, returns dict with >= 5 categories
- `test_structure_is_category_then_language` — each value is a dict with "EN" and/or "FR" keys, each containing a list of strings
- `test_keywords_are_lowercased` — all keywords in all categories are lowercase
- `test_category_counts_match` — "Core Language and Translation" has >= 15 EN keywords and >= 14 FR keywords (from CSV analysis)
- `test_fails_on_missing_file` — SystemExit on nonexistent path
- `test_fails_on_empty_keywords` — SystemExit on CSV with headers only

**Class `TestSelectKeywordBatch`:**
- `test_selects_up_to_per_language` — given 10 EN + 10 FR keywords, returns exactly 10 (5+5)
- `test_fewer_than_limit_uses_all` — given 3 FR keywords with per_language=5, returns all 3 FR + 5 EN = 8
- `test_empty_language_skipped` — category with only EN keywords returns just EN batch
- `test_randomness` — call twice with large pool, results differ (statistical; use `random.seed` for reproducibility in other tests)
- `test_returns_flat_list` — result is a flat list of strings, not nested

### Task 2: Rewrite `bidsandtenders_scrape()` with keyword search logic
**Files:** `scraper/pipeline/bidsandtenders.py`, `scraper/tests/test_bidsandtenders.py`
**Action:** MODIFY (bidsandtenders.py), CREATE (test_bidsandtenders.py)

**Modify `bidsandtenders_scrape()` signature and return type:**

Create a `BidsAndTendersResult` named tuple (or dataclass) at the top of `bidsandtenders.py`:
```python
from typing import NamedTuple

class BidsAndTendersResult(NamedTuple):
    listings: list[ProcurementListing]
    search_used: bool  # True if keyword search was performed, False if fell back to full scrape
```

Update the function signature:
```python
async def bidsandtenders_scrape(
    portal: PortalRecord,
    keywords_by_category: dict[str, dict[str, list[str]]] | None = None,
) -> BidsAndTendersResult:
```

The `search_used` flag tells the orchestrator (Plan 7-02) whether to apply post-extraction keyword filtering. When the search box is not found, `search_used=False` and the orchestrator MUST still apply keyword filtering (per CONTEXT.md: "Search box not found: fall back to current behavior, apply post-extraction keyword filter").

**Add three helper functions (private, in same file):**

**`async def _find_search_input(page) -> locator | None`**
- Try selectors in order: `page.get_by_role("searchbox")`, `page.get_by_placeholder("Search")`, `page.locator("input[type='text']").first`
- For each, check `await locator.is_visible(timeout=3000)`
- Return first visible locator, or `None` if none found
- Log warning if none found

**`async def _execute_search(page, query: str) -> str`**
- Find search input via `_find_search_input(page)`
- Clear any existing text: `await search_input.fill("")`
- Fill with query: `await search_input.fill(query)`
- Press Enter: `await search_input.press("Enter")`
- Wait: `await page.wait_for_load_state("networkidle")` then `await page.wait_for_timeout(3000)`
- Return `await page.content()`

**`async def _reset_search(page) -> None`**
- Try to find and click reset: `page.get_by_text("Reset", exact=False)`
- If visible, click and wait for networkidle + 2s timeout
- If not visible, navigate back to the listing URL as fallback (the page object carries the URL)

**Main search loop in `bidsandtenders_scrape()`:**

After the existing page.goto() and initial wait:

1. Try to find search input. If not found OR keywords_by_category is None, fall back to original behavior (get page.content(), extract, return `BidsAndTendersResult(listings=..., search_used=False)`).

2. Try to set results limit to 100: look for a "100" option in the page (e.g., `page.get_by_text("100")` near a "Limit Results" area). If found and visible, click it, wait for reload. If not found, continue with default limit. Do NOT fail if this doesn't work.

3. Loop over `keywords_by_category.items()`:
   - Call `select_keyword_batch(category_keywords)` to get random batch
   - If `or_supported` is True (starts True), build OR query: `" OR ".join(batch)`
     - Call `_execute_search(page, or_query)` -> html
     - Extract listings via `extract_listings_from_html(html, portal.name)`
     - If zero listings: set `or_supported = False`, fall through to individual searches
     - If listings found: extend `all_listings`, call `_reset_search(page)`, continue to next category
   - If `or_supported` is False (individual fallback):
     - For each keyword in batch: `_reset_search(page)`, `_execute_search(page, keyword)`, extract, extend `all_listings`
   - After each category, call `_reset_search(page)`

4. Deduplicate `all_listings` using `deduplicate_listings()` from `keywords.py` -- BUT wait, `deduplicate_listings()` works on `ListingRecord` objects (it reads `.source_listing_id`). `ProcurementListing` also has `.source_listing_id`. Check: yes, `ProcurementListing` has `source_listing_id` field. The dedup function accesses `.source_listing_id` which exists on both types. So we can reuse it directly on `ProcurementListing` objects.

5. Return `BidsAndTendersResult(listings=deduplicated_list, search_used=True)`.

6. Add `import random` and `from scraper.pipeline.keywords import select_keyword_batch, deduplicate_listings` to imports.

**Create `scraper/tests/test_bidsandtenders.py`:**

All Playwright interactions must be mocked. Use `unittest.mock.AsyncMock` for async page methods.

Helper: Create a mock page factory that simulates Playwright page behavior:
```python
def _make_mock_page(search_visible=True, html_content="<html>...</html>"):
    page = AsyncMock()
    # ... configure get_by_role, get_by_placeholder, locator, fill, press, etc.
    page.content.return_value = html_content
    return page
```

**Class `TestFindSearchInput`:**
- `test_finds_by_role` — searchbox role locator is visible, returns it
- `test_falls_back_to_placeholder` — role not visible, placeholder visible, returns placeholder
- `test_falls_back_to_input_type` — role and placeholder not visible, input[type=text] visible, returns it
- `test_returns_none_when_nothing_found` — all selectors not visible, returns None

**Class `TestExecuteSearch`:**
- `test_fills_and_presses_enter` — verifies fill() called with query and press("Enter") called
- `test_waits_for_networkidle` — verifies wait_for_load_state("networkidle") called
- `test_returns_page_content` — returns the HTML string from page.content()

**Class `TestKeywordSearch` (integration-level, mocked Playwright):**
- `test_or_query_constructed_correctly` — mock page, mock extract_listings_from_html to return listings, verify the OR-joined query was typed
- `test_multiple_categories_searched` — provide 3 categories, verify 3 search calls made (with reset between)
- `test_results_aggregated_across_categories` — 2 categories each return 3 listings, verify 6 total (before dedup)
- `test_results_deduplicated` — overlapping source_listing_ids across categories, verify dedup removes duplicates

**Class `TestSearchFallback`:**
- `test_or_zero_results_triggers_individual` — OR query extract returns [], verify individual keyword searches executed
- `test_fallback_persists_across_categories` — first category OR fails, second category goes straight to individual (no OR attempt)
- `test_individual_searches_reset_between` — verify _reset_search called between individual keyword searches

**Class `TestSearchBoxNotFound`:**
- `test_no_search_box_falls_back_to_full_scrape` — _find_search_input returns None, verify original behavior (extract from full page content)
- `test_no_search_box_returns_search_used_false` — verify `result.search_used is False` when search box not found
- `test_no_keywords_falls_back_to_full_scrape` — keywords_by_category=None, verify original behavior
- `test_no_keywords_returns_search_used_false` — verify `result.search_used is False` when no keywords

**Class `TestBidsAndTendersScrapeSignature`:**
- `test_keywords_parameter_is_optional` — calling with just portal still works (backward compatible)
- `test_returns_bidsandtenders_result` — verify return type is `BidsAndTendersResult` with `listings` and `search_used` fields
- `test_search_used_true_when_search_performed` — verify `result.search_used is True` when keywords provided and search box found

## Verification

**Task 1 verify:** `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py -x -q`
**Task 2 verify:** `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py scraper/tests/test_bidsandtenders.py -x -q`

**Expected:** All tests pass (existing keyword tests + new category/batch tests + new bidsandtenders tests)
**Gate:** `load_keywords_by_category()` returns correct structure from real CSV, `select_keyword_batch()` selects correct counts, `bidsandtenders_scrape()` returns `BidsAndTendersResult` with correct `search_used` flag, keyword searches use OR queries with fallback, search box not found gracefully falls back to full scrape with `search_used=False`, results are deduplicated
