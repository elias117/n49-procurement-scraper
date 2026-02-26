# Phase 8 Plan 1 — Browser-Use Keyword Search Logic

**Phase Goal:** Generic browser-use portals search for keywords using portal search forms instead of scraping all visible listings.
**Plan Goal:** Rewrite `browser_scrape()` to perform keyword searches via sequential browser-use Agent runs, with OR-query fallback, action history inspection for search_used detection, and comprehensive error handling. Add config setting and create `test_browser_scraper.py`.
**Requirements:** FILT-03, FILT-04
**Depends on:** Phase 6 complete (keyword module + dedup exist)

## Context

The current `browser_scrape()` (137 lines in `scraper/pipeline/browser_scraper.py`) creates a browser-use Agent with a broad prompt that explicitly says "Do not fill in search forms." Phase 8 flips that — the agent actively finds and uses search forms to query keywords, filtering at the source.

**Architecture: Sequential Agent runs, shared Browser**

Each keyword batch (6 total, one per category) gets its own Agent instance, all sharing the same `Browser` with `keep_alive=True`. This works because browser-use preserves the browser page state between Agent instances when `keep_alive=True`.

- **First Agent run (~20 steps):** Navigate to portal, find search form/page, type first keyword batch, submit.
- **Subsequent Agent runs (~6 steps each):** Clear search box, type next keyword batch, submit.
- **Step budget:** 50 total. First run gets `min(20, remaining)`, subsequent get `min(6, remaining)`. Stop creating new Agent runs when budget exhausted.

**OR query strategy:** Same as Phase 7. Try OR-joined keywords first. If a category returns zero listings, set `or_supported=False` and retry that category + all subsequent categories with single first-keyword searches.

**Search detection:** Inspect `history.action_names()` for `"input_text"` — definitive proof the agent typed into a field.

**Fallback:** If the first Agent run produces no `input_text` action, the agent never found a search form. Return whatever listings are on the page with `search_used=False`.

Key locked decisions from CONTEXT.md:
- 6 searches per portal, one per category, 5 random keywords per batch, EN+FR
- 50 max steps total across all searches
- Agent seeks any search/filter interface (text boxes, dropdowns, panels)
- Agent clicks to reveal hidden search bars (magnifying glass, expandable panels)
- Agent navigates to Search/Advanced Search pages if linked
- Clear search box between searches (don't re-navigate)
- Silent fallback if no keywords provided (original behavior)
- Partial success = search worked; crash mid-way = return collected results
- Detailed per-portal logging

Key files to reference:
- `scraper/pipeline/browser_scraper.py` — scraper to rewrite
- `scraper/pipeline/bidsandtenders.py` — reference implementation for search pattern
- `scraper/pipeline/keywords.py` — `select_keyword_batch`, `deduplicate_listings`
- `scraper/pipeline/extraction.py` — `extract_listings_from_html()`
- `scraper/config.py` — add new config setting
- `scraper/models.py` — `ProcurementListing` return type

## Tasks

### Task 1: Add `BROWSER_SEARCH_MAX_STEPS` to config.py
**File:** `scraper/config.py`
**Action:** MODIFY

Add a new config setting below `BROWSER_MAX_STEPS`:

```python
BROWSER_SEARCH_MAX_STEPS: int = int(
    os.environ.get("BROWSER_SEARCH_MAX_STEPS", "50")
)
```

This is the total step budget for keyword search across all Agent runs on a single portal. The existing `BROWSER_MAX_STEPS` (10) remains for the no-keyword fallback path.

### Task 2: Rewrite `browser_scrape()` with keyword search logic
**File:** `scraper/pipeline/browser_scraper.py`
**Action:** MODIFY

**1. Add imports:**
```python
from typing import NamedTuple
from scraper.pipeline.keywords import select_keyword_batch, deduplicate_listings
```

**2. Create `BrowserScrapeResult` NamedTuple** (after the existing imports, before the function):
```python
class BrowserScrapeResult(NamedTuple):
    """Result from a browser-use scrape with search metadata."""
    listings: list[ProcurementListing]
    search_used: bool  # True if keyword search was performed
```

**3. Update `browser_scrape()` signature:**
```python
async def browser_scrape(
    portal: PortalRecord,
    keywords_by_category: dict[str, dict[str, list[str]]] | None = None,
) -> BrowserScrapeResult:
```

**4. Add helper function `_detect_search_used(history) -> bool`** (private, before `browser_scrape`):
```python
def _detect_search_used(history) -> bool:
    """Check if agent action history contains text input (proof of search)."""
    if history is None:
        return False
    try:
        action_names = history.action_names()
        return "input_text" in action_names
    except Exception:
        return False
```

**5. Implement the main function logic:**

The function body should follow this structure:

```
A. Lazy import browser-use (same as current)
B. If no keywords_by_category: run original behavior (navigate to listings, extract, return BrowserScrapeResult(listings, search_used=False))
C. If keywords provided: run keyword search path
```

**No-keyword path (B):** Same as current code but return `BrowserScrapeResult(listings, search_used=False)` instead of bare list. Use `config.BROWSER_MAX_STEPS` (10) for the step budget. Keep the current prompt ("Do not fill in search forms").

**Keyword search path (C):**

```python
# Build keyword batches
batches = []
for cat_name, cat_kw in keywords_by_category.items():
    batch = select_keyword_batch(cat_kw)
    if batch:
        batches.append((cat_name, batch))

if not batches:
    # Edge case: all categories empty after batch selection
    # Fall through to no-keyword behavior
    ...

all_listings: list[ProcurementListing] = []
search_detected = False
total_steps = 0
or_supported = True
searches_completed = 0

for i, (cat_name, batch) in enumerate(batches):
    remaining_budget = config.BROWSER_SEARCH_MAX_STEPS - total_steps
    if remaining_budget <= 0:
        logger.warning(
            "Step budget exhausted (%d/%d) for '%s' after %d/%d searches",
            total_steps, config.BROWSER_SEARCH_MAX_STEPS,
            portal.name, searches_completed, len(batches),
        )
        break

    # Build query based on OR support
    if or_supported:
        query = " OR ".join(batch)
    else:
        query = batch[0]  # Single keyword fallback

    # Build agent task
    if i == 0:
        # First search: navigate + find search + type keywords
        task = (
            f"Navigate to {portal.url}. "
            f"Look for a search form, search box, or Advanced Search page for "
            f"procurement opportunities, tenders, or bids. "
            f"If you see a 'Search' or 'Advanced Search' link, click on it. "
            f"If there's a hidden search bar (magnifying glass icon or expandable panel), "
            f"click to reveal it. "
            f"Once you find a search input, type: {query} "
            f"Submit the search by pressing Enter or clicking the search/submit button. "
            f"Stop when you can see search results or a list of opportunities."
        )
        max_steps = min(remaining_budget, 20)
    else:
        # Subsequent searches: clear and re-search
        task = (
            f"On this page, find the search box or search input. "
            f"Clear any existing text in it. "
            f"Type: {query} "
            f"Submit the search by pressing Enter or clicking the search/submit button. "
            f"Stop when you can see search results."
        )
        max_steps = min(remaining_budget, 8)

    try:
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
            browser=browser,
            use_vision=False,
        )
        history = await agent.run(max_steps=max_steps)

        steps_used = history.number_of_steps() if history else 0
        total_steps += steps_used

        # Check if agent typed into a field
        if _detect_search_used(history):
            search_detected = True

        # Extract listings from current page
        page = await browser.get_current_page()
        if page is not None:
            html = await page.content()
            listings = extract_listings_from_html(html, portal.name)

            if or_supported and not listings and search_detected:
                # OR query may not be supported — retry with single keyword
                or_supported = False
                query = batch[0]
                logger.info(
                    "OR query returned 0 results for '%s' category '%s', "
                    "falling back to single keyword: '%s'",
                    portal.name, cat_name, query,
                )
                # Retry this category with single keyword
                remaining_budget = config.BROWSER_SEARCH_MAX_STEPS - total_steps
                if remaining_budget > 0:
                    retry_agent = Agent(
                        task=(
                            f"Clear the search box. Type: {query} "
                            f"Submit the search. Stop when you see results."
                        ),
                        llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
                        browser=browser,
                        use_vision=False,
                    )
                    retry_history = await retry_agent.run(
                        max_steps=min(remaining_budget, 8)
                    )
                    total_steps += retry_history.number_of_steps() if retry_history else 0
                    page = await browser.get_current_page()
                    if page is not None:
                        html = await page.content()
                        listings = extract_listings_from_html(html, portal.name)

            all_listings.extend(listings)
            searches_completed += 1

            logger.info(
                "Portal '%s' category '%s': %d listings found (%s query, %d steps)",
                portal.name, cat_name, len(listings),
                "OR" if or_supported else "single",
                steps_used,
            )

    except Exception:
        logger.exception(
            "Search failed for portal '%s' category '%s'",
            portal.name, cat_name,
        )
        # Continue to next category — don't lose collected results

# Determine search_used
if not search_detected:
    # Agent never found a search form — return whatever is on the page
    logger.info(
        "No search form detected for '%s', returning visible listings (fallback)",
        portal.name,
    )

# Deduplicate across all categories
deduplicated = deduplicate_listings(all_listings)

logger.info(
    "Browser keyword search complete for '%s': "
    "%d/%d searches completed, %d total listings, %d after dedup, "
    "%d steps used, search_used=%s",
    portal.name, searches_completed, len(batches),
    len(all_listings), len(deduplicated),
    total_steps, search_detected,
)

return BrowserScrapeResult(listings=deduplicated, search_used=search_detected)
```

**6. Error handling:** Wrap the entire keyword search path in try/except. On exception, return `BrowserScrapeResult(listings=all_listings_collected_so_far, search_used=search_detected)` — NOT empty list. The `finally` block still kills the browser (same as current).

**7. Update the no-keyword path error handling:** Change `return []` to `return BrowserScrapeResult(listings=[], search_used=False)` everywhere the current code returns early.

### Task 3: Create `scraper/tests/test_browser_scraper.py`
**File:** `scraper/tests/test_browser_scraper.py`
**Action:** CREATE

All browser-use dependencies (Agent, Browser, ChatOpenAI, history) are mocked. Tests verify logic, not browser-use internals.

**Helper fixtures/factories:**

```python
@pytest.fixture
def generic_portal():
    return PortalRecord(
        id="portal-gen-001", name="BC Bid",
        url="https://www.bcbid.gov.bc.ca", level="provincial",
        province="British Columbia", language="en",
        requires_login=False, enabled=True,
    )

@pytest.fixture
def sample_keywords_by_category():
    return {
        "Core Language": {"EN": ["translation", "interpreter", "linguist", "bilingual", "french"],
                          "FR": ["traduction", "interprète", "linguiste", "bilingue", "français"]},
        "Communications": {"EN": ["communications", "engagement", "outreach", "media", "public"],
                           "FR": ["communications", "engagement", "sensibilisation", "médias", "public"]},
    }
```

Mock factory for browser-use Agent:
```python
def _make_mock_history(action_names_list=None, steps=3):
    """Create a mock AgentHistoryList."""
    history = MagicMock()
    history.action_names.return_value = action_names_list or []
    history.number_of_steps.return_value = steps
    return history
```

**Class `TestDetectSearchUsed`:**
- `test_detects_input_text_in_history` — history with `["go_to_url", "input_text", "click_element"]` returns True
- `test_no_input_text_returns_false` — history with `["go_to_url", "click_element"]` returns False
- `test_none_history_returns_false` — None history returns False
- `test_exception_in_history_returns_false` — history.action_names() raises, returns False

**Class `TestBrowserScrapeNoKeywords`:**
All tests patch `browser_use.Agent`, `browser_use.Browser`, etc. at the module import level.

- `test_no_keywords_uses_original_prompt` — keywords_by_category=None, verify Agent task contains "Do not fill in search forms"
- `test_no_keywords_returns_search_used_false` — verify `result.search_used is False`
- `test_no_keywords_returns_browser_scrape_result` — verify return type has `listings` and `search_used` fields
- `test_no_keywords_uses_standard_max_steps` — verify `agent.run(max_steps=config.BROWSER_MAX_STEPS)` (10, not 50)

**Class `TestBrowserScrapeKeywordSearch`:**
- `test_first_search_prompt_includes_navigate_and_keywords` — first Agent task contains portal URL and keyword terms
- `test_first_search_prompt_mentions_advanced_search` — task mentions "Advanced Search"
- `test_subsequent_search_prompt_says_clear` — second+ Agent tasks contain "Clear" and new keywords
- `test_six_categories_produce_six_agent_runs` — 6 categories → 6 Agent() instantiations (with mocked history showing input_text)
- `test_step_budget_limits_searches` — set BROWSER_SEARCH_MAX_STEPS=15, first search uses 12 steps, second search uses 5 steps → only 2 searches attempted
- `test_search_detected_sets_search_used_true` — history has `input_text` → `result.search_used is True`
- `test_listings_collected_across_categories` — 2 categories each return 3 listings → 6 total before dedup
- `test_results_deduplicated` — overlapping source_listing_ids → fewer results after dedup

**Class `TestBrowserScrapeOrFallback`:**
- `test_or_query_used_first` — first query contains " OR " joining keywords
- `test_or_zero_results_falls_back_to_single` — first search returns 0 listings → retry with single keyword
- `test_or_fallback_persists_across_categories` — after OR fails on first category, subsequent categories use single keyword (no " OR " in query)

**Class `TestBrowserScrapeFallback`:**
- `test_no_search_form_returns_search_used_false` — history has no `input_text` → `result.search_used is False`
- `test_no_search_form_returns_visible_listings` — agent navigates but doesn't search, listings from page still returned
- `test_exception_mid_search_returns_collected_results` — first search succeeds (3 listings), second search throws → result contains the 3 listings
- `test_crash_returns_collected_not_empty` — partial results returned, not empty list

**Class `TestBrowserScrapeResult`:**
- `test_result_has_listings_and_search_used` — verify NamedTuple fields
- `test_result_unpacks_correctly` — `listings, search_used = result` works

## Verification

**Command:** `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_browser_scraper.py -x -q`
**Expected:** All tests pass
**Gate:** `browser_scrape()` returns `BrowserScrapeResult` with correct `search_used` flag; keyword searches use OR with single-keyword fallback; action history inspected for `input_text`; step budget enforced; partial results preserved on failure; no-keyword path unchanged except return type; detailed logging present
