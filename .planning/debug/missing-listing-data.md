---
status: awaiting_human_verify
trigger: "Most listings have missing descriptions, missing dates, missing dollar values, missing contact information, and the source URL doesn't link back to the original listing on their respective portal."
created: 2026-03-02T12:00:00Z
updated: 2026-03-02T12:10:00Z
---

## Current Focus

hypothesis: CONFIRMED - BidsAndTenders scraper (~29 portals, the largest group) only extracted from listing/summary pages and never visited individual detail pages. Fix applied: detail page enrichment added to bidsandtenders.py.
test: All 227 tests pass (211 original + 16 new). New tests cover _is_sparse, _resolve_url, _merge_detail, _enrich_with_details (including edge cases), and integration tests for both full-scrape and keyword-search paths.
expecting: BidsAndTenders listings now enriched with full details from individual detail pages
next_action: Awaiting human verification that fix works in production environment

## Symptoms

expected: Every listing should have: description (full text from portal), dates (posting/closing dates), dollar values (contract amounts), contact information, and a working source_url that links back to the original listing on the portal where it was found.
actual: Most listings across portals have empty/missing descriptions, dates, money values, and contact info. The link/source_url doesn't point to the original listing page on the portal.
errors: Fields appear silently empty/null
reproduction: Look at any listings in the database or dashboard - most have missing fields
started: Unclear if always been this way or recent regression. System has been live since ~2026-02-24.

## Eliminated

## Evidence

- timestamp: 2026-03-02T12:00:30Z
  checked: All three scraper architectures
  found: Three scraper types exist:
    1. CanadaBuys (canadabuys.py) - CSV download, maps all CSV columns including description, dates, contact, source_url. This should be complete.
    2. BidsAndTenders (bidsandtenders.py, ~29 portals) - Playwright, navigates to listing page, extracts via LLM. NO detail page visit logic at all. Only calls extract_listings_from_html() on the listing page HTML.
    3. Browser-use (browser_scraper.py, ~13 portals) - browser-use Agent, has _enrich_with_details() for detail pages (added by SEAO fix). But SEAO fix is still "awaiting_human_verify".
  implication: BidsAndTenders is the largest group and has NO detail page enrichment. Browser scraper has it but fix is pending verification.

- timestamp: 2026-03-02T12:01:00Z
  checked: SEAO debug session (.planning/debug/seao-incomplete-listings.md)
  found: Root cause confirmed and fix applied for browser_scraper.py: strip_html now preserves href, detail page enrichment added. Status: awaiting_human_verify. Fix includes _is_sparse, _enrich_with_details, _merge_detail.
  implication: Browser scraper fix exists but BidsAndTenders has the SAME fundamental problem with zero fix applied.

- timestamp: 2026-03-02T12:02:00Z
  checked: BidsAndTenders scraper code in detail
  found: bidsandtenders_scrape() has TWO code paths:
    1. No keywords / no search box found: navigates to {base_url}/Module/Tenders/en, gets full page HTML, calls extract_listings_from_html(). NO detail page visits.
    2. Keyword search path: searches categories, extracts from search result pages, deduplicates. NO detail page visits.
    In BOTH paths, the scraper only sees the listing/summary page. BidsAndTenders portals show a table of tenders with title, closing date, and maybe status. Full details (description, value, contact) are only on individual tender detail pages.
  implication: This is the exact same problem as browser_scraper had before the SEAO fix: no detail page enrichment.

- timestamp: 2026-03-02T12:02:30Z
  checked: CanadaBuys scraper (canadabuys.py)
  found: CanadaBuys downloads a CSV with ALL fields already mapped - description, dates, contact, source_url (notice_url) are all explicit CSV columns. This scraper should be producing complete data.
  implication: CanadaBuys is NOT affected by the missing data issue. Only browser-based scrapers (BidsAndTenders + browser-use) are affected.

- timestamp: 2026-03-02T12:03:00Z
  checked: source_url handling across all scrapers
  found:
    - CanadaBuys: Maps notice_url CSV column directly to source_url. Working correctly.
    - BidsAndTenders: source_url is extracted by LLM from listing page HTML. But listing pages show a table -- the LLM may extract the portal URL itself or nothing. Individual listing URLs need to be discovered from the table links. The strip_html fix (from SEAO session) preserves href on <a> tags, which helps the LLM see individual listing links. But without visiting detail pages, this only gets the link, not the content.
    - Browser-use: Same as BidsAndTenders. The SEAO fix added href preservation in strip_html and detail page enrichment.
  implication: source_url extraction depends on strip_html preserving hrefs (already fixed in SEAO session), and the LLM being able to see listing links in the table.

- timestamp: 2026-03-02T12:03:30Z
  checked: validation.py source_url handling
  found: validation.py Rule 8 nullifies source_url if it doesn't start with http:// or https://. This is correct behavior but means relative URLs from LLM extraction will be lost. The browser_scraper has _resolve_url() to handle relative URLs. BidsAndTenders does NOT.
  implication: Even if the LLM extracts relative URLs from BidsAndTenders listing pages, they'll be nullified by validation. Need URL resolution before validation.

- timestamp: 2026-03-02T12:04:00Z
  checked: Portal count breakdown
  found:
    - 1 CanadaBuys portal (CSV download, complete data)
    - ~29 BidsAndTenders portals (NO detail page enrichment)
    - ~13 browser-use portals (detail page enrichment added by SEAO fix, pending verification)
    - ~20 portals are MERX/SEAO (requires_login=true, were disabled, enabled by migration 008)
    Total: BidsAndTenders is the largest group of enabled, accessible portals, and it has NO detail page enrichment.
  implication: The majority of scraped listings come from BidsAndTenders portals, which explains why "most listings" have missing data.

- timestamp: 2026-03-02T12:05:00Z
  checked: Fix implementation and test results
  found: Added detail page enrichment to bidsandtenders.py following the same pattern as browser_scraper.py. Functions added: _is_sparse(), _resolve_url(), _merge_detail(), _enrich_with_details(). Wired into both code paths (full scrape and keyword search). All 227 tests pass (211 original + 16 new).
  implication: Fix is code-complete and unit-tested. Needs production verification.

## Resolution

root_cause: The BidsAndTenders scraper (~29 portals, the largest group) only extracts data from listing/summary pages and never visits individual tender detail pages. BidsAndTenders listing pages show a table with minimal information (title, closing date, status) while full details (description, dollar values, contact information, documents) are only available on individual tender detail pages. This is the same fundamental issue that was identified and fixed for the browser-use scraper in the SEAO debug session, but was never addressed for BidsAndTenders.

Additionally, source_url is unreliable because:
1. The LLM may extract relative URLs from the listing page table links
2. Validation nullifies any non-absolute URLs
3. There was no URL resolution step for BidsAndTenders (now added via _resolve_url)

fix: Added detail page enrichment to bidsandtenders.py, mirroring the approach in browser_scraper.py:
  1. _is_sparse() identifies listings missing descriptions (the primary detail field).
  2. _resolve_url() resolves relative URLs against the portal base URL.
  3. _merge_detail() merges detail page data into sparse listings, preserving original title and non-null fields.
  4. _enrich_with_details() navigates to detail pages via Playwright, extracts full data via extract_listing_detail(), and merges enriched data. Respects BROWSER_DETAIL_MAX_PAGES config (default 10).
  5. Enrichment wired into BOTH code paths: full page scrape (no keywords/no search box) and keyword search (after dedup).

verification: All 227 tests pass (211 original + 16 new). New tests cover:
  - _is_sparse: sparse when no description, not sparse when description present, sparse with only closing_date
  - _resolve_url: absolute URL passthrough, relative URL resolution, no-leading-slash resolution
  - _merge_detail: fills None fields from detail, does not overwrite existing values, preserves original title
  - _enrich_with_details: enriches sparse listings with URLs, skips non-sparse, skips sparse without URL, respects max_pages config, handles extraction failure gracefully, handles navigation error gracefully
  - Integration: full scrape path enriches sparse listings, keyword search path enriches sparse listings

files_changed:
  - scraper/pipeline/bidsandtenders.py (added _is_sparse, _resolve_url, _merge_detail, _enrich_with_details; wired enrichment into both scrape paths; added extract_listing_detail import and urljoin import)
  - scraper/tests/test_bidsandtenders.py (added 16 new tests for all new functions and integration)
