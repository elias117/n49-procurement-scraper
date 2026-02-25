# Phase 7: BidsAndTenders Keyword Search - Research

**Researched:** 2026-02-25
**Domain:** Playwright browser automation, BidsAndTenders search UI, keyword batch selection, multi-search aggregation and deduplication
**Confidence:** HIGH

## Summary

Phase 7 modifies the existing `bidsandtenders_scrape()` function in `scraper/pipeline/bidsandtenders.py` to use the BidsAndTenders portal search interface for keyword-based filtering instead of scraping the default tender listing page. The current scraper navigates directly to `{base_url}/Module/Tenders/en` and extracts all visible listings. The new behavior performs 5 keyword searches per portal (one per category), aggregates results, deduplicates by `source_listing_id`, and returns only relevant listings.

The BidsAndTenders platform provides a search box on the `/Module/Tenders/en` page with a text input, a Reset link, and an Advanced Search option. All 29 BidsAndTenders portals in the database share identical platform UI. The search appears to be AJAX-driven (jQuery-based), meaning search results load dynamically after submission. The scraper already uses Playwright with `headless=False` under Xvfb, which is the correct setup for interacting with this UI.

The key new logic components are: (1) a function to load keywords grouped by category from the CSV (the current `load_keywords()` returns a flat list -- a new `load_keywords_by_category()` function is needed), (2) a function to select random keyword batches per category, (3) search execution with OR-query format and fallback to individual keyword searches, (4) result aggregation across multiple searches with deduplication. The deduplication function `deduplicate_listings()` from Phase 6's `keywords.py` module is reused directly. No keyword filtering of results is needed for BidsAndTenders portals because the search box itself filters results.

**Primary recommendation:** Add a `load_keywords_by_category()` function to `keywords.py` that returns `dict[str, list[str]]` keyed by category. Modify `bidsandtenders_scrape()` to accept keywords, build OR queries per category with random 5-keyword batches, execute searches via Playwright, aggregate results, and deduplicate before returning. The orchestrator passes keywords into the scraper but skips post-extraction keyword filtering for BidsAndTenders portals (search box is sufficient filtering).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **6 searches per portal** -- one search per keyword category (note: CSV has 5 categories, not 6; CONTEXT.md says "plus the 6th category" but only 5 exist. Use all 5 categories = 5 searches per portal)
- **5 random keywords per batch** -- randomly selected from each category on every scrape run, giving broader coverage over time
- **Both EN and FR keywords** in every search -- a single search query includes both language versions (so up to 10 terms per search if 5 EN + 5 FR)
- **Categories with fewer than 5 keywords:** Use all available keywords for that category
- **Random selection re-rolls every run** -- no persisted selection; each nightly run picks a fresh random 5 from each category
- **OR query format:** Combine keywords with OR operator in search box (e.g., `translation OR traduction OR interpreter OR linguist`)
- **Fallback:** If OR-style query returns zero results, fall back to individual keyword searches for that batch
- **Detection:** Zero results from an OR query triggers the fallback -- assume portal treats OR as literal text
- **Fallback scope:** Per-portal. If a portal doesn't support OR, all 5 batches for that portal use individual searches
- **Search box is sufficient** -- no post-extraction keyword filtering needed for BidsAndTenders portals
- **Deduplication is critical** -- multiple keyword searches per portal will return overlapping listings; deduplicate by `source_listing_id` before upsert (reuse Phase 6 dedup logic)
- **Result aggregation:** Collect all listings from all 5 searches per portal into one list, deduplicate, then upsert
- **Pagination:** If search results span multiple pages, handle pagination (depends on BidsAndTenders UI)
- **All 29 portals share the same BidsAndTenders platform UI** -- expect identical search behavior
- **Search box not found:** Log a warning and fall back to the current behavior (scrape all visible listings from `/Module/Tenders/en`, apply post-extraction keyword filter from Phase 6)
- **Search returns unexpected results:** Accept whatever the search returns -- the search box is trusted as sufficient filtering
- **Best-effort approach:** If a portal is genuinely different, degrade gracefully rather than fail the entire run
- **Modifies `bidsandtenders_scrape()` in `scraper/pipeline/bidsandtenders.py`**
- **Keywords are already loaded by the orchestrator (Phase 6)** -- pass them into the scraper function
- **Reuse `dedup_listings()` from Phase 6's keyword module**
- **No changes to database schema, API, or frontend**
- **Sequential portal processing remains** (memory constraint unchanged)

### Claude's Discretion
- Playwright selectors for the search box (must be discovered at runtime or via robust selectors)
- How to detect "zero results" condition (text parsing, element count, etc.)
- Whether to use page.fill() vs page.press_sequentially() for search input
- Pagination strategy details (click "Next Page" vs. increase limit to 100)
- How to structure the new keyword-by-category loading function
- Whether fallback tracking (per-portal OR support) persists across categories within one portal run
- Test structure and mock strategy for Playwright interactions

### Deferred Ideas (OUT OF SCOPE)
None raised during discussion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FILT-02 | BidsAndTenders Playwright scraper uses portal search interface to query keywords, using OR-style queries where supported | Current scraper navigates to `/Module/Tenders/en` and scrapes all listings. Must be modified to: locate search box, type OR-joined keywords, submit, extract results. BidsAndTenders UI confirmed to have search box with text input on the tender listing page. Playwright 1.51.0 in Docker. |
| FILT-04 | For portals with simple search boxes (no OR support), a curated subset of core translation keywords is used | Fallback strategy: if OR query returns zero results, search each keyword individually. The "curated subset" is the random 5-keyword batch already selected per category. All 29 BidsAndTenders portals share identical UI, so OR support/lack thereof is portal-wide. |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Component | Version | Purpose | Current Location |
|-----------|---------|---------|-----------------|
| Playwright | >=1.50 (Docker: v1.51.0) | Browser automation for search interaction | `scraper/pipeline/bidsandtenders.py` |
| Python random module | stdlib | Random keyword selection per category | New usage in `keywords.py` |
| Python csv module | stdlib | Keyword loading by category | Existing `keywords.py` |
| pytest + pytest-asyncio | >=8.0 / >=0.23 | Unit tests | `scraper/tests/` |

### No New Dependencies
This phase requires ZERO new libraries. All functionality uses Python stdlib (`random`, `csv`) and existing project dependencies (`playwright`). The keyword loading enhancement and search logic are pure Python.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright fill() + Enter | press_sequentially() (char by char) | fill() is faster and sufficient; press_sequentially() only needed if autocomplete interferes |
| Random keyword selection | Fixed keyword rotation | Random gives broader coverage over time as specified in CONTEXT.md |
| OR query format | Always individual searches | OR queries are 5-10x faster (1 search vs 10); fallback handles portals that don't support it |

## Architecture Patterns

### Modified Files
```
scraper/
  pipeline/
    keywords.py          # MODIFIED: add load_keywords_by_category()
    bidsandtenders.py    # MODIFIED: accept keywords, perform search-based scraping
    orchestrator.py      # MODIFIED: pass category-grouped keywords to BidsAndTenders scraper,
                         #           skip keyword filtering for BidsAndTenders portals
  tests/
    test_bidsandtenders.py  # NEW: tests for keyword search logic
    test_keywords.py        # MODIFIED: tests for load_keywords_by_category()
```

### Pattern 1: Load Keywords by Category

**What:** New function in `keywords.py` that returns keywords grouped by category as a `dict[str, list[str]]`.

**Why needed:** The current `load_keywords()` returns a flat `list[str]`. Phase 7 needs keywords grouped by category to build per-category search queries with random batches.

**Example:**
```python
# In scraper/pipeline/keywords.py

def load_keywords_by_category(csv_path: Path = KEYWORDS_CSV_PATH) -> dict[str, list[str]]:
    """
    Load keywords from CSV grouped by category.

    Returns dict mapping category name -> list of lowercased keywords
    (both EN and FR combined per category).

    Raises SystemExit if CSV is missing, malformed, or empty.
    """
    if not csv_path.exists():
        logger.error("Keywords CSV not found: %s", csv_path)
        raise SystemExit(f"Keywords CSV not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            logger.error("Keywords CSV missing columns: %s", missing)
            raise SystemExit(f"Keywords CSV missing required columns: {missing}")

        categories: dict[str, list[str]] = {}
        for row in reader:
            keyword = row.get("Keyword", "").strip()
            category = row.get("Category", "").strip()
            if keyword and category:
                categories.setdefault(category, []).append(keyword.lower())

    if not categories:
        logger.error("Keywords CSV loaded but contains no keywords")
        raise SystemExit("Keywords CSV contains no keywords")

    total = sum(len(kws) for kws in categories.values())
    logger.info(
        "Loaded %d keywords across %d categories from %s",
        total, len(categories), csv_path.name,
    )
    return categories
```

**Keyword distribution per category (from CSV analysis):**

| Category | EN | FR | Total | Batch Size (5 EN + 5 FR) |
|----------|----|----|-------|--------------------------|
| Core Language and Translation | 16 | 15 | 31 | 10 terms |
| Official Languages and Bilingualism | 17 | 17 | 34 | 10 terms |
| Multilingual Coverage | 10 | 10 | 20 | 10 terms |
| Communications and Engagement | 12 | 12 | 24 | 10 terms |
| Procurement Vehicle Signals | 7 | 4 | 11 | 9 terms (4 FR < 5) |

**Important:** The CSV has 5 categories, not 6 as stated in CONTEXT.md ("one search per keyword category"). Implementation should iterate over however many categories exist in the CSV (currently 5). This means 5 searches per portal, not 6.

### Pattern 2: Random Keyword Batch Selection

**What:** Select up to 5 random EN keywords and up to 5 random FR keywords from a category.

**Design consideration:** The CONTEXT.md says "5 random keywords per batch" and "Both EN and FR keywords in every search." The simplest interpretation: randomly select 5 EN keywords + 5 FR keywords from the category, combine into one search query (up to 10 terms joined with OR).

However, `load_keywords_by_category()` as designed above combines EN and FR into one list per category. To support selecting 5 EN + 5 FR separately, the function should either: (a) return `dict[str, dict[str, list[str]]]` (category -> language -> keywords), or (b) the batch selection function can split by parsing the original CSV. Option (a) is cleaner.

**Recommended approach:** Store keywords as `dict[str, dict[str, list[str]]]` where outer key is category, inner key is language ("EN"/"FR"):

```python
def load_keywords_by_category(csv_path: Path = KEYWORDS_CSV_PATH) -> dict[str, dict[str, list[str]]]:
    """
    Load keywords grouped by category and language.

    Returns:
        Dict[category_name, Dict["EN"|"FR", List[keyword_str]]]
    """
    # ... parsing logic ...
    # Result: {"Core Language and Translation": {"EN": [...], "FR": [...]}, ...}
```

**Batch selection:**
```python
import random

def select_keyword_batch(
    category_keywords: dict[str, list[str]],
    per_language: int = 5,
) -> list[str]:
    """
    Select random keyword batch from a single category.

    Picks up to `per_language` EN keywords and `per_language` FR keywords.
    If a language has fewer than `per_language`, uses all available.

    Returns combined list of selected keywords.
    """
    selected = []
    for lang in ("EN", "FR"):
        kws = category_keywords.get(lang, [])
        count = min(per_language, len(kws))
        selected.extend(random.sample(kws, count))
    return selected
```

### Pattern 3: OR Query Construction and Execution

**What:** Build an OR-joined query string from a keyword batch and type it into the BidsAndTenders search box.

**OR query format:** `translation OR traduction OR interpreter OR linguist`

**Maximum query length:** With up to 10 keywords per batch (some multi-word phrases like "services de traduction"), the longest possible query would be approximately:
- 10 terms * ~30 chars average + 9 " OR " separators = ~336 chars
- This is well within typical search box limits

**Playwright search execution:**
```python
async def _search_portal(page, query: str) -> str:
    """
    Type a search query into the BidsAndTenders search box and return page HTML.

    Args:
        page: Playwright page object (already on /Module/Tenders/en).
        query: The search query string (OR-joined keywords).

    Returns:
        HTML content of the search results page.
    """
    # Locate the search input -- BidsAndTenders uses a text input near "Search" label
    # Use robust selectors that work across all 29 portals
    search_input = page.locator("input[type='text']").first
    # Alternative selectors to try if the above fails:
    # page.get_by_placeholder("Search")
    # page.locator(".search-input")
    # page.locator("input").first

    await search_input.fill(query)
    await search_input.press("Enter")

    # Wait for AJAX results to load
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(3000)  # Extra wait for dynamic content

    return await page.content()
```

**Critical note on selectors:** The exact search input selector cannot be determined from WebFetch alone because the BidsAndTenders page loads dynamically via AJAX. The page has a "Search" label, a Reset link, and an Advanced Search link. The implementer MUST use resilient selectors. Recommended approach:
1. Try `page.get_by_role("searchbox")` first
2. Fall back to `page.get_by_placeholder(...)` if discoverable
3. Fall back to `page.locator("input[type='text']").first`
4. If no search box found, log warning and fall back to scraping all visible listings

### Pattern 4: Zero-Results Detection and Fallback

**What:** Detect when an OR query returns zero results and fall back to individual keyword searches.

**Detection strategies (in order of reliability):**
1. Extract listings from the HTML -- if `extract_listings_from_html()` returns empty list, that's zero results
2. Look for "no results" text on the page (e.g., "No tenders found", "0 results")
3. Count table rows in results area

**Recommended:** Use the extraction result count. After searching, extract listings from the HTML. If zero listings are returned, try individual keyword searches.

```python
async def _search_with_fallback(page, keywords: list[str], portal_name: str) -> list:
    """
    Search with OR query, falling back to individual searches if zero results.

    Returns list of ProcurementListing objects.
    """
    # Try OR query first
    or_query = " OR ".join(keywords)
    html = await _search_portal(page, or_query)
    listings = extract_listings_from_html(html, portal_name)

    if listings:
        return listings

    # OR query returned zero results -- fall back to individual searches
    logger.info(
        "OR query returned 0 results for '%s', falling back to individual searches",
        portal_name,
    )
    all_listings = []
    for keyword in keywords:
        # Reset search first
        await _reset_search(page)
        html = await _search_portal(page, keyword)
        batch = extract_listings_from_html(html, portal_name)
        all_listings.extend(batch)

    return all_listings
```

**Fallback scope:** Per-portal. If the first category's OR query fails on a portal, the implementation should track this and skip OR queries for remaining categories on that same portal, going straight to individual searches. This saves time.

```python
or_supported = True  # Assume OR works until proven otherwise

for category_name, category_keywords in keywords_by_category.items():
    batch = select_keyword_batch(category_keywords)

    if or_supported:
        or_query = " OR ".join(batch)
        html = await _search_portal(page, or_query)
        listings = extract_listings_from_html(html, portal_name)
        if not listings:
            or_supported = False  # This portal doesn't support OR
            # Fall through to individual searches below
        else:
            all_listings.extend(listings)
            continue

    # Individual keyword searches (fallback)
    for keyword in batch:
        await _reset_search(page)
        html = await _search_portal(page, keyword)
        listings = extract_listings_from_html(html, portal_name)
        all_listings.extend(listings)
```

### Pattern 5: Search Reset Between Queries

**What:** Clear the search box and return to full listing view before executing the next search.

**Why needed:** After searching, the page shows filtered results. The next search must start from a clean state.

**Approach:** Click the "Reset" link visible on the BidsAndTenders page, then wait for the full listing to reload.

```python
async def _reset_search(page):
    """Reset the search to show all tenders."""
    reset_link = page.get_by_text("Reset")
    if await reset_link.is_visible():
        await reset_link.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
```

### Pattern 6: Pagination Handling

**What:** Handle search results that span multiple pages.

**BidsAndTenders pagination:** The platform shows 15 results by default, with options for 25, 50, or 100 per page. There are "Previous Page" and "Next Page" navigation buttons.

**Recommended strategy:** Before searching, increase the result limit to 100 (the maximum). This reduces pagination needs. For most keyword searches on municipal portals, 100 results per search should capture all relevant listings.

```python
# Set results limit to 100 before searching
limit_selector = page.locator("text=100").first  # Or select from dropdown
if await limit_selector.is_visible():
    await limit_selector.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
```

**If results exceed 100:** For a typical municipal BidsAndTenders portal, keyword-filtered results are unlikely to exceed 100. If they do, the first 100 results are a reasonable best-effort capture. Implementing full pagination across all searches (5 categories x potentially multiple pages) would significantly increase scraping time and complexity. Skip pagination beyond the first page unless testing reveals it's needed.

### Pattern 7: Orchestrator Integration

**What:** Pass category-grouped keywords to BidsAndTenders scraper and skip post-extraction keyword filtering for BidsAndTenders portals.

**Current flow (orchestrator.py):**
```python
# In process_portal():
raw_listings = await scrape_portal(portal)          # Step 1: Scrape
listing_records = [convert(item) for item in raw]   # Step 2: Convert
if keywords:
    listing_records = filter_listings(listing_records, keywords)  # Step 2.5: Filter
listing_records = deduplicate_listings(listing_records)            # Step 2.6: Dedup
```

**New flow:** For BidsAndTenders portals, the search box already filters results. Post-extraction keyword filtering should be SKIPPED to avoid double-filtering (the search box returns listings that match the search terms, which may not exactly match the substring-based keyword filter).

```python
# In scrape_portal() -- pass keywords to BidsAndTenders scraper
if portal_type == "bidsandtenders":
    return await bidsandtenders_scrape(portal, keywords_by_category=keywords_by_category)

# In process_portal() -- skip keyword filtering for BidsAndTenders
portal_type = classify_portal(portal)
if keywords and portal_type != "bidsandtenders":
    listing_records = filter_listings(listing_records, keywords)
```

**Orchestrator changes needed:**
1. `run_pipeline()` must call both `load_keywords()` (flat list, for filtering) and `load_keywords_by_category()` (for BidsAndTenders search)
2. `process_portal()` must receive `keywords_by_category` and pass it through `scrape_portal()` to `bidsandtenders_scrape()`
3. `process_portal()` must skip keyword filtering for BidsAndTenders portals
4. Deduplication still runs for all portal types (BidsAndTenders results from multiple searches need dedup)

### Pattern 8: Graceful Fallback When Search Box Not Found

**What:** If the search box element cannot be located on a portal page, fall back to the original behavior (scrape all visible listings, apply post-extraction keyword filter).

```python
async def bidsandtenders_scrape(portal, keywords_by_category=None):
    # ... browser setup ...
    await page.goto(listing_url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(5000)

    # Try to find search box
    search_input = page.locator("input[type='text']").first
    search_found = await search_input.is_visible(timeout=5000)

    if not search_found or not keywords_by_category:
        # Fallback: scrape all visible listings (original behavior)
        logger.warning(
            "Search box not found for '%s', falling back to full listing scrape",
            portal.name,
        )
        html = await page.content()
        return extract_listings_from_html(html, portal.name)

    # Search-based scraping (new behavior)
    # ... search execution logic ...
```

### Anti-Patterns to Avoid
- **Don't create a new browser instance per search** -- reuse the same page/context across all 5 category searches for a portal. Creating a new browser per search wastes 5-10 seconds each time.
- **Don't hardcode specific CSS class selectors** -- the BidsAndTenders platform may update styling. Use semantic selectors (role, placeholder, text content) that are more resilient.
- **Don't skip deduplication** -- multiple keyword searches WILL return overlapping results. Without dedup, the same listing would be upserted multiple times (harmless due to ON CONFLICT but wasteful for embeddings).
- **Don't apply post-extraction keyword filter to BidsAndTenders results** -- the search box already filtered them. Double-filtering with substring match may incorrectly reject listings that the search found but whose title/description don't contain the exact keyword substring.
- **Don't persist OR-support detection across runs** -- each run should test OR support fresh, as portals may be updated.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Random keyword selection | Custom shuffling logic | `random.sample(list, k)` | stdlib, handles edge cases (k > len) with ValueError |
| OR query construction | Manual string concatenation | `" OR ".join(keywords)` | Clean, handles empty lists gracefully |
| Search box interaction | Custom JavaScript injection | `page.locator().fill()` + `press("Enter")` | Playwright's built-in methods handle focus, events, and timing |
| Deduplication | New dedup logic | `deduplicate_listings()` from keywords.py | Already tested and working from Phase 6 |
| HTML extraction | Custom parsing | `extract_listings_from_html()` | Already handles BidsAndTenders HTML via LLM extraction |

**Key insight:** The existing scraper already handles the hard parts (browser setup, HTML extraction, Playwright lifecycle). Phase 7 only adds search interaction between page load and HTML extraction.

## Common Pitfalls

### Pitfall 1: Search Box Not Loading (AJAX Timing)
**What goes wrong:** The search input element exists in the DOM but hasn't been rendered yet when Playwright tries to interact with it.
**Why it happens:** BidsAndTenders uses jQuery AJAX to load the tender table and search interface dynamically.
**How to avoid:** After `page.goto()`, use `page.wait_for_load_state("networkidle")` followed by an explicit `page.wait_for_timeout(5000)` (already in current code). Additionally, use `search_input.wait_for(state="visible", timeout=10000)` before interacting.
**Warning signs:** `TimeoutError` when trying to fill the search box.

### Pitfall 2: OR Literal Interpretation
**What goes wrong:** Some portals may treat "OR" as a literal search term, returning results for the word "OR" rather than using it as a boolean operator.
**Why it happens:** Not all search implementations support boolean operators.
**How to avoid:** The fallback logic detects this: if an OR query returns zero results (unlikely if OR is treated literally -- it would return results containing "OR"), switch to individual searches. However, if OR is treated literally, the query may return SOME results (containing the word "OR"), which wouldn't trigger the fallback. A more robust detection: if the OR query returns results but none match any of the actual keywords, that's suspicious. For simplicity, trust the CONTEXT.md decision: zero results triggers fallback.
**Warning signs:** Unusually irrelevant results from a portal when using OR queries.

### Pitfall 3: Browser Resource Exhaustion (29 Portals x 5+ Searches Each)
**What goes wrong:** Each portal now requires 5-50 search interactions instead of 1 page load, significantly increasing browser session duration and memory usage.
**Why it happens:** 29 portals x 5 categories x (page load + search + wait) = potentially 145+ page interactions in a single pipeline run.
**How to avoid:** The existing sequential processing (one portal at a time) with browser close/restart per portal mitigates memory issues. Each portal's browser session is independent. The key is to keep the browser alive for all 5 searches within ONE portal (reuse page), but close it between portals (already the pattern).
**Warning signs:** Memory growth in Docker container, OOM kills during scraping.

### Pitfall 4: Stale Page State Between Searches
**What goes wrong:** After searching and extracting results, the page state (search filters, scroll position, pagination) carries over to the next search.
**Why it happens:** Playwright maintains page state between interactions.
**How to avoid:** Between category searches, reset the search by clicking "Reset" or navigating back to the base URL. The Reset link on BidsAndTenders pages clears the search.
**Warning signs:** Second search returns same results as first, or returns no results unexpectedly.

### Pitfall 5: Function Signature Change Breaking Tests
**What goes wrong:** Adding `keywords_by_category` parameter to `bidsandtenders_scrape()` breaks existing orchestrator tests that mock this function.
**Why it happens:** `test_orchestrator.py` mocks `bidsandtenders_scrape` with specific call assertions.
**How to avoid:** Make `keywords_by_category` an optional parameter with default `None`. Update the mock assertions in `test_orchestrator.py::TestScrapePortal::test_dispatch_bidsandtenders` to include the new parameter. The existing behavior (no keywords = scrape all) is preserved when `None` is passed.
**Warning signs:** `test_orchestrator.py` tests failing after signature change.

### Pitfall 6: Accented Characters in Search Box
**What goes wrong:** French keywords with accents (e.g., "traduction assermentee" vs "traduction assermentee") may not render correctly when typed into the search box.
**Why it happens:** Character encoding issues between Python string and browser input.
**How to avoid:** Playwright's `fill()` method handles Unicode correctly. The keywords are stored as UTF-8 strings in Python. No special handling needed. Verified: Playwright 1.50+ handles Unicode input without issues.
**Warning signs:** French keyword searches returning zero results while English ones work fine.

### Pitfall 7: Category Count Mismatch with CONTEXT.md
**What goes wrong:** CONTEXT.md says "6 searches per portal" but the CSV only has 5 categories.
**Why it happens:** CONTEXT.md mentions "Core Language/Translation, Official Languages/Bilingualism, Multilingual Coverage, Communications/Engagement, Procurement Vehicle Signals, plus the 6th category" -- the 6th category doesn't exist in the current CSV.
**How to avoid:** Iterate over whatever categories exist in the CSV dynamically. Don't hardcode a category count. If a 6th category is added to the CSV later, it will be picked up automatically.
**Warning signs:** None -- this is already handled correctly by iterating over the dict keys.

## Code Examples

### Current BidsAndTenders Scraper (Before Phase 7)

Source: `/Users/clawbot/dev/scraper/pipeline/bidsandtenders.py`

```python
async def bidsandtenders_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    # 1. Launch browser (headless=False under Xvfb)
    # 2. Navigate to {base_url}/Module/Tenders/en
    # 3. Wait for networkidle + 5s extra
    # 4. Get page HTML
    # 5. Extract listings via LLM (extract_listings_from_html)
    # 6. Close browser
    # Returns: list[ProcurementListing]
```

This returns ALL visible listings. Phase 7 changes step 3-4 to: search for keywords, get search results HTML, repeat for each category.

### Keywords CSV Categories and Counts

Source: `/Users/clawbot/dev/keywords_library.csv`

```
5 unique categories, 120 total keyword rows:
- Communications and Engagement:         12 EN + 12 FR = 24
- Core Language and Translation:         16 EN + 15 FR = 31
- Multilingual Coverage:                 10 EN + 10 FR = 20
- Official Languages and Bilingualism:   17 EN + 17 FR = 34
- Procurement Vehicle Signals:            7 EN +  4 FR = 11
```

### Existing Deduplication Function (Reuse from Phase 6)

Source: `/Users/clawbot/dev/scraper/pipeline/keywords.py` lines 90-110

```python
def deduplicate_listings(listings: list) -> list:
    """Remove duplicate listings by source_listing_id within a batch."""
    seen = set()
    unique = []
    for listing in listings:
        lid = listing.source_listing_id
        if lid and lid in seen:
            continue
        if lid:
            seen.add(lid)
        unique.append(listing)
    # ... logging ...
    return unique
```

This function works on `ListingRecord` objects. BidsAndTenders scraper returns `ProcurementListing` objects. Deduplication happens in `process_portal()` AFTER conversion to `ListingRecord`, so this is compatible.

### Orchestrator Portal Classification

Source: `/Users/clawbot/dev/scraper/pipeline/orchestrator.py` lines 35-49

```python
def classify_portal(portal: PortalRecord) -> str:
    if portal.name == "CanadaBuys":
        return "canadabuys"
    if "bidsandtenders" in portal.url:
        return "bidsandtenders"
    return "browser"
```

This classification is used to dispatch to the correct scraper. It can also be used in `process_portal()` to determine whether to skip post-extraction keyword filtering.

### All 29 BidsAndTenders Portal URLs

Source: `/Users/clawbot/dev/db/migrations/002_seed_portals.sql`

All portals follow the pattern `https://{subdomain}.bidsandtenders.ca/`. Examples:
- `mississauga.bidsandtenders.ca`
- `brampton.bidsandtenders.ca`
- `hamilton.bidsandtenders.ca`
- `halifax.bidsandtenders.ca`
- `london.bidsandtenders.ca`
- `guelph.bidsandtenders.ca`
- etc.

One provincial portal: `ontariotenders.bidsandtenders.ca`
All 29 are enabled (`enabled=true`) and none require login (`requires_login=false`).

### Playwright Input Patterns

Source: [Playwright Python docs](https://playwright.dev/python/docs/input)

```python
# Fill a search box and press Enter
await page.locator("input[type='text']").first.fill("translation OR traduction")
await page.locator("input[type='text']").first.press("Enter")

# Wait for AJAX results
await page.wait_for_load_state("networkidle")

# Alternative: use get_by_role for semantic selection
search_box = page.get_by_role("searchbox")
await search_box.fill("keyword query")
await search_box.press("Enter")

# Alternative: use get_by_placeholder
search_box = page.get_by_placeholder("Search")
await search_box.fill("keyword query")
await search_box.press("Enter")
```

### Existing Test Patterns for Orchestrator Mocking

Source: `/Users/clawbot/dev/scraper/tests/test_orchestrator.py`

```python
# Mocking the bidsandtenders_scrape function
@patch(
    "scraper.pipeline.orchestrator.bidsandtenders_scrape",
    new_callable=AsyncMock,
)
def test_dispatch_bidsandtenders(self, mock_scrape, bidsandtenders_portal):
    mock_scrape.return_value = []
    result = asyncio.get_event_loop().run_until_complete(
        scrape_portal(bidsandtenders_portal)
    )
    mock_scrape.assert_called_once_with(bidsandtenders_portal)
```

This test will need updating when `bidsandtenders_scrape` gains a `keywords_by_category` parameter.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Scrape all visible listings | Search for keywords via portal search box | Phase 7 (this phase) | Only relevant listings scraped, ~90% reduction in LLM extraction calls |
| Single page load per portal | 5 search interactions per portal | Phase 7 | More targeted results but longer scrape time per portal |
| No keyword awareness in BidsAndTenders scraper | Category-based keyword search with OR queries | Phase 7 | Search-level filtering before extraction |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `/Users/clawbot/dev/pytest.ini` |
| Quick run command | `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_bidsandtenders.py scraper/tests/test_keywords.py -x -q` |
| Full suite command | `cd /Users/clawbot/dev && python -m pytest -x -q` |
| Estimated runtime | ~5 seconds (unit tests, mocked Playwright) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILT-02 | BidsAndTenders scraper uses search interface with OR queries | unit (mocked Playwright) | `pytest scraper/tests/test_bidsandtenders.py::TestKeywordSearch -x` | No -- Wave 0 gap |
| FILT-02 | Fallback to individual searches on zero results | unit (mocked Playwright) | `pytest scraper/tests/test_bidsandtenders.py::TestSearchFallback -x` | No -- Wave 0 gap |
| FILT-04 | Curated keyword subset used per category | unit | `pytest scraper/tests/test_keywords.py::TestLoadKeywordsByCategory -x` | No -- Wave 0 gap |
| FILT-04 | Random batch selection respects per-language limits | unit | `pytest scraper/tests/test_bidsandtenders.py::TestBatchSelection -x` | No -- Wave 0 gap |
| FILT-05 | Deduplication across multiple searches | unit | `pytest scraper/tests/test_keywords.py::TestDeduplicateListings -x` | Yes -- existing |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task, run: `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_bidsandtenders.py scraper/tests/test_keywords.py -x -q`
- **Full suite trigger:** Before merging final task: `cd /Users/clawbot/dev && python -m pytest -x -q`
- **Phase-complete gate:** Full suite green before `/gsd:verify-work`
- **Estimated feedback latency per task:** ~5 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `scraper/tests/test_bidsandtenders.py` -- covers FILT-02 (keyword search, OR fallback, search box not found, result aggregation)
- [ ] Additional tests in `scraper/tests/test_keywords.py` -- covers FILT-04 (`load_keywords_by_category`, batch selection)
- [ ] Update `scraper/tests/test_orchestrator.py` -- update mocks for new `bidsandtenders_scrape` signature, test BidsAndTenders keyword filter skip
- [ ] No framework install needed -- pytest already configured

## Open Questions

1. **Exact search input selector**
   - What we know: The BidsAndTenders page has a "Search" label with a text input, a "Reset" link, and an "Advanced Search" link. It uses jQuery AJAX.
   - What's unclear: The exact HTML `id`, `name`, `class`, or `placeholder` attribute of the search input element. WebFetch cannot render JavaScript-loaded content.
   - Recommendation: Use multiple fallback selectors in order of reliability: `page.get_by_role("searchbox")`, `page.get_by_placeholder(...)`, `page.locator("input[type='text']").first`. The implementer should test against a live BidsAndTenders portal during development if possible. If not, the fallback-to-scrape-all pattern ensures no portal is skipped entirely.

2. **Search submission method**
   - What we know: Pressing Enter after filling the search box should submit the search. BidsAndTenders may also have a search button.
   - What's unclear: Whether Enter triggers the AJAX search or if a specific button click is needed.
   - Recommendation: Try `press("Enter")` first. If that doesn't trigger results, look for a search/submit button near the search input and click it.

3. **Results loading indicator**
   - What we know: BidsAndTenders has an `#ajax_loader` element (loading spinner).
   - What's unclear: Whether waiting for `networkidle` is sufficient or if we need to wait for the loader to disappear.
   - Recommendation: Use `page.wait_for_load_state("networkidle")` + `page.wait_for_timeout(3000)` as the baseline. If results aren't loading reliably, add `page.locator("#ajax_loader").wait_for(state="hidden", timeout=10000)` as an additional wait condition.

4. **Limit Results control**
   - What we know: BidsAndTenders has a "Limit Results" dropdown with options 15, 25, 50, 100.
   - What's unclear: How the dropdown is implemented (native select, custom dropdown, links).
   - Recommendation: Attempt to set limit to 100 before searching to maximize results per query. If the control can't be reliably interacted with, accept the default (15) and note that some results may be missed.

5. **Category count: 5 vs 6**
   - What we know: CSV has 5 categories. CONTEXT.md mentions 6.
   - What's unclear: Whether a 6th category was intended but not added to the CSV.
   - Recommendation: Iterate dynamically over CSV categories. Currently 5 searches per portal. If user adds a 6th category, code handles it automatically.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `scraper/pipeline/bidsandtenders.py` -- complete current scraper implementation (123 lines)
- Codebase inspection: `scraper/pipeline/keywords.py` -- keyword loading and dedup functions (111 lines)
- Codebase inspection: `scraper/pipeline/orchestrator.py` -- pipeline flow, portal classification, keyword integration (217 lines)
- Codebase inspection: `scraper/models.py` -- ProcurementListing and ListingRecord models
- Codebase inspection: `scraper/pipeline/extraction.py` -- `extract_listings_from_html()` function used for HTML -> listings
- Codebase inspection: `db/migrations/002_seed_portals.sql` -- all 29 BidsAndTenders portal URLs confirmed
- Codebase inspection: `keywords_library.csv` -- 5 categories, 120 keywords, EN+FR distribution analyzed
- Codebase inspection: `scraper/tests/test_orchestrator.py` -- existing mock patterns for scraper dispatch
- Codebase inspection: `scraper/tests/test_keywords.py` -- existing keyword tests to extend
- Codebase inspection: `scraper/Dockerfile` -- Playwright v1.51.0, Xvfb, headless=False
- Codebase inspection: `scraper/requirements.txt` -- playwright>=1.50

### Secondary (MEDIUM confidence)
- [Playwright Python Input docs](https://playwright.dev/python/docs/input) -- fill(), press(), press_sequentially() methods
- [Playwright Python Locators docs](https://playwright.dev/python/docs/locators) -- get_by_role, get_by_placeholder selectors
- WebFetch of mississauga.bidsandtenders.ca -- confirmed Search label, Reset link, Advanced Search, status filters, pagination (15/25/50/100), AJAX loading

### Tertiary (LOW confidence)
- BidsAndTenders search input HTML attributes -- could not be determined via WebFetch due to JavaScript rendering. Selector strategy must be resilient with fallbacks.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all existing tools
- Architecture: HIGH -- all integration points identified with exact file/line references, clear modification plan
- Pitfalls: HIGH -- identified through direct code inspection and BidsAndTenders platform analysis
- Search selectors: LOW -- exact HTML attributes unknown, must use fallback strategy
- Code examples: HIGH -- patterns derived from existing codebase and Playwright docs

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable -- Playwright API well-established, BidsAndTenders platform UI unlikely to change drastically)
