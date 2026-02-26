# Phase 8 Context — Browser-Use Portals Keyword Search

## Keyword Search Strategy

- **6 searches per portal** — one search per keyword category, identical to Phase 7
- **5 random keywords per batch** — randomly selected from each category on every scrape run, both EN and FR (up to 10 terms per search)
- **Random selection re-rolls every run** — no persisted selection; each nightly run picks a fresh random 5 from each category
- **OR query first** — combine keywords with OR operator; fall back to fewer terms if the portal's search box doesn't handle it
- **Single browser session per portal** — agent navigates once, finds the search form, runs all 6 keyword searches sequentially in that same session
- **Same `keywords_by_category` parameter** — reuse the same interface and format as BidsAndTenders (Phase 7); no new parameter format needed

## Agent Behavior & Step Budget

- **50 max steps** per portal session (covers: navigate → find search → 6 keyword rounds → read results)
- **Search form discovery:** Agent should look for any search/filter interface — text boxes, dropdowns, filter panels, whatever the portal offers
- **Click to reveal:** Agent should attempt to open hidden search bars (magnifying glass icons, expandable search panels, etc.)
- **Seek out search pages:** If the listings page has a "Search" or "Advanced Search" link, navigate to it before attempting keyword entry
- **Clear search box between searches** — don't navigate back to search page; clear the input and type the next query
- **No keywords provided:** Silently fall back to current behavior (scrape all visible listings, no search attempt, no error)

## Fallback Triggers & Behavior

Three scenarios trigger fallback to post-extraction keyword filtering:

1. **No search form found** — agent navigated the portal, couldn't find any search/filter interface
2. **Search form found but broken** — agent used it but got errors, empty page, or page didn't respond
3. **All 6 keyword searches returned zero results** — search technically worked but found nothing

In all fallback cases, the agent returns whatever listings are visible on the page, and the orchestrator applies post-extraction keyword filtering (Phase 6 logic).

**Partial success handling:**
- If some keyword searches return results and others return zero → `search_used=True` (search worked overall)
- If agent hits the 50-step limit mid-way through searches → keep collected results, mark search as used for completed searches
- If agent crashes mid-way → return whatever was collected so far (not empty list)

## Search Outcome Detection

- **Inspect agent action history** to determine if search was performed — look for evidence the agent typed into a search field (definitive proof, not self-reporting)
- **`search_used` flag logic:** If action history shows text input into a search/filter element → `True`; otherwise → `False`
- **Detailed logging per portal:** Log search form found/not found, number of searches completed out of 6, total listings collected, and whether fallback was triggered
- **Same orchestrator interface:** `browser_scrape()` returns `(listings, search_used)` tuple, matching the pattern established by BidsAndTenders in Phase 7

## Architecture Notes

- Modifies `browser_scrape()` in `scraper/pipeline/browser_scraper.py`
- Agent prompt changes from "Do not fill in search forms" to actively seeking and using search forms
- Keywords passed via orchestrator using `keywords_by_category` (same as Phase 7)
- Reuse `dedup_listings()` from Phase 6's keyword module
- No changes to database schema, API, or frontend
- Sequential portal processing remains (memory constraint unchanged)

## Deferred Ideas

(None raised during discussion)

---
*Created: 2026-02-25*
