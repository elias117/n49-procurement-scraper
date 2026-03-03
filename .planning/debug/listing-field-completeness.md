---
status: awaiting_human_verify
trigger: "Most listings have missing descriptions, missing dates, missing money values, missing contact information, and the source_url doesn't link back to the original listing on the portal where it was found."
created: 2026-03-02T15:00:00Z
updated: 2026-03-02T15:05:00Z
---

## Current Focus

hypothesis: CONFIRMED -- All 3 actionable code fixes are applied and tested. The uncommitted _is_sparse broadening is the final piece. All 237 tests pass.
test: Verified all code changes, ran all tests
expecting: Human verification that fix works in production
next_action: Awaiting human verification, then commit the uncommitted _is_sparse changes and archive all 4 debug sessions

## Symptoms

expected: Every listing should have: description (full text from portal), closing_date, value_min/value_max (contract amounts), contact_info, and a working source_url that links back to the original listing page on the portal where it was found.
actual: Most listings across portals have empty/missing descriptions, dates, money values, and contact info. The link/source_url doesn't point to the original listing page on the portal.
errors: Fields appear silently empty/null - no errors thrown
reproduction: Look at any listings in the database - most have missing fields
timeline: Has always been this way since the system was built. Never worked correctly.

## Eliminated

## Evidence

- timestamp: 2026-03-02T15:00:30Z
  checked: State of all 3 prior debug sessions
  found: |
    1. listing-data-gaps.md (status: fixing) -- Comprehensive analysis found 5 root causes:
       - value_min/value_max: NOT fixable (data not available from source portals)
       - contact_info: Partially fixable (detail page enrichment + broadened _is_sparse)
       - source_url: Partially fixable (strip_html href preservation + _resolve_url)
       - closing_date: Will improve with enrichment
       - description: MERX blocked by login, others improve with enrichment
       Actionable fix identified: broaden _is_sparse() in both scrapers
    2. missing-listing-data.md (status: awaiting_human_verify) -- BidsAndTenders detail page enrichment applied
    3. seao-incomplete-listings.md (status: awaiting_human_verify) -- Browser scraper detail page enrichment + strip_html href fix applied
  implication: The enrichment infrastructure is in place. The _is_sparse broadening was the one remaining code fix from listing-data-gaps.

- timestamp: 2026-03-02T15:01:00Z
  checked: Uncommitted code changes (git diff HEAD)
  found: |
    4 files changed, 138 insertions, 20 deletions:
    - bidsandtenders.py: _is_sparse broadened (None -> 3 conditions: None, <50 chars, missing both date+contact)
    - browser_scraper.py: _is_sparse broadened (identical logic)
    - test_bidsandtenders.py: 8 new/updated tests for broadened _is_sparse + updated skip_non_sparse test
    - test_browser_scraper.py: 8 new/updated tests for broadened _is_sparse + updated skip_non_sparse test
    All 237 tests pass.
  implication: The _is_sparse broadening fix from listing-data-gaps session is already implemented and tested. This was the LAST actionable code fix.

- timestamp: 2026-03-02T15:01:30Z
  checked: Complete fix inventory across all sessions
  found: |
    Fixes already applied (committed):
    - strip_html() href preservation in extraction.py (commit ffa37a3 or d441b70)
    - Detail page enrichment in browser_scraper.py (_is_sparse, _resolve_url, _merge_detail, _enrich_with_details)
    - Detail page enrichment in bidsandtenders.py (same pattern)
    - BROWSER_DETAIL_MAX_PAGES config

    Fixes applied (uncommitted, in working tree):
    - Broadened _is_sparse() in both scrapers (3 conditions instead of 1)
    - Corresponding test updates

    NOT fixable (data availability):
    - value_min/value_max: Source portals don't publish dollar amounts
    - MERX portals: Login barrier prevents content access
    - CanadaBuys source_url: CSV data often has empty URL columns
  implication: All actionable code fixes are in place. The uncommitted changes are the final piece.

## Resolution

root_cause: Five independent issues cause field completeness gaps across all portals:

  1. **Detail page enrichment was missing (FIXED):** Both BidsAndTenders (~29 portals) and browser-use scrapers (~13 portals) only extracted from listing/summary pages, never visiting detail pages. Detail pages contain descriptions, contact info, closing dates. Fixed by adding _enrich_with_details() to both scrapers.

  2. **strip_html removed URLs (FIXED):** The HTML stripping function removed href attributes from <a> tags, preventing the LLM from discovering detail page URLs. Fixed by preserving href as inline "[url]" text.

  3. **_is_sparse was too conservative (FIXED - uncommitted):** _is_sparse() only triggered on `description is None`, missing listings with short descriptions or listings that had descriptions but lacked contact_info and closing_date. Broadened to trigger on: no description, description < 50 chars, or missing both closing_date and contact_name.

  4. **value_min/value_max (NOT FIXABLE):** Canadian procurement portals (CanadaBuys CSV, BidsAndTenders, browser portals) rarely or never publish contract dollar amounts in tender notices. This is a data availability limitation across all sources, not a code bug.

  5. **MERX portals blocked by login (NOT FIXABLE via code):** MERX requires authentication. The requires_login field is stored but no scraper handles it. MERX portals return near-empty listings.

fix: Three code changes across 3 prior debug sessions address all fixable issues:
  1. strip_html() preserves href on <a> tags (extraction.py) -- committed
  2. Detail page enrichment added to both scrapers (bidsandtenders.py, browser_scraper.py) -- committed
  3. Broadened _is_sparse() in both scrapers to trigger on more conditions -- UNCOMMITTED, needs to be committed

verification: All 237 tests pass (including 16+ new tests for enrichment and 16+ new/updated tests for broadened _is_sparse). All test names and assertions verified.

files_changed:
  - scraper/pipeline/extraction.py (strip_html href preservation)
  - scraper/pipeline/browser_scraper.py (detail enrichment + broadened _is_sparse)
  - scraper/pipeline/bidsandtenders.py (detail enrichment + broadened _is_sparse)
  - scraper/config.py (BROWSER_DETAIL_MAX_PAGES)
  - scraper/tests/test_browser_scraper.py (enrichment + _is_sparse tests)
  - scraper/tests/test_bidsandtenders.py (enrichment + _is_sparse tests)
