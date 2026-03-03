---
status: awaiting_human_verify
trigger: "SEAO scraper is producing listings with only a name but no other information"
created: 2026-03-02T00:00:00Z
updated: 2026-03-02T00:05:00Z
---

## Current Focus

hypothesis: CONFIRMED - browser_scraper only extracted from listing page, never visited detail pages. strip_html also removed all URLs preventing detail page discovery.
test: Applied fix, all 211 tests pass (194 original + 17 new)
expecting: SEAO listings now enriched with full details from individual detail pages
next_action: Awaiting human verification

## Symptoms

expected: SEAO listings should have full details - description, closing date, organization, value, URL, etc.
actual: Some SEAO listings show up with only the tender name and the source (e.g., "Longueuil SEAO") but no other details
errors: Unknown - need to investigate scraper output and logs
reproduction: Check scraped SEAO listings in the database/output - look for ones with minimal data
started: Since SEAO portals were enabled (migration 008)

## Eliminated

## Evidence

- timestamp: 2026-03-02T00:00:30Z
  checked: Project structure and scraper architecture
  found: SEAO portals (Longueuil SEAO, Laval SEAO, Gatineau SEAO, etc.) all point to https://www.seao.ca/ and are classified as "browser" type. They use browser_scraper.py.
  implication: SEAO uses the generic browser scraper path

- timestamp: 2026-03-02T00:00:45Z
  checked: browser_scraper.py code flow
  found: browser_scrape() navigates to the portal URL, gets listing page HTML, calls extract_listings_from_html(). There is NO step that visits individual listing detail pages. The extract_listing_detail() function exists in extraction.py but is NEVER called from browser_scraper.py.
  implication: Scraper only sees summary data from listing page, not full details

- timestamp: 2026-03-02T00:00:50Z
  checked: extraction.py strip_html function
  found: strip_html removes ALL HTML attributes including href on <a> tags. This means even if listing pages contain links to detail pages, the URLs are stripped before the LLM sees them. The LLM cannot extract source_url because links are gone.
  implication: Double failure - (1) no detail page visits AND (2) URLs stripped so LLM can't even discover detail page URLs

- timestamp: 2026-03-02T00:00:55Z
  checked: SEAO portal configuration
  found: Multiple SEAO portals exist, all pointing to same URL, all require_login=true, all were enabled by migration 008.
  implication: All SEAO portals affected by the same root cause

- timestamp: 2026-03-02T00:01:00Z
  checked: extract_listing_detail() in extraction.py
  found: Function exists, is tested, but never imported or called from browser_scraper.py or orchestrator.py. It's dead code ready to be wired in.
  implication: The capability to extract from detail pages already exists but was never connected

## Resolution

root_cause: Two interconnected issues cause SEAO listings to have only titles:
  1. strip_html() in extraction.py removes ALL HTML attributes including href on <a> tags, so the LLM cannot extract source_url links to detail pages.
  2. browser_scraper.py only extracts from the listing/summary page and never navigates to individual detail pages. The extract_listing_detail() function exists but was never wired into the browser scraper pipeline.

  Result: Procurement portals like SEAO show minimal info on listing pages (title, maybe organization) with full details (description, dates, amounts, contacts) only on individual tender detail pages. The scraper extracts only from the listing page, producing title-only listings.

fix: Three changes applied:
  1. Modified strip_html() to preserve href attributes on <a> tags, converting them to inline "[url]" text format so the LLM can discover detail page URLs during extraction.
  2. Added detail page enrichment to browser_scraper.py: _is_sparse() identifies listings missing key details, _enrich_with_details() visits detail pages via the browser, extract_listing_detail() extracts full data, and _merge_detail() combines detail data with original listing data.
  3. Added BROWSER_DETAIL_MAX_PAGES config (default 10) to control how many detail pages are visited per scrape run.

verification: All 211 tests pass (194 original + 17 new). New tests cover _is_sparse, _resolve_url, _merge_detail, _enrich_with_details (including edge cases: non-sparse skip, no-URL skip, max pages limit, detail extraction failure, navigation error). strip_html URL preservation verified manually and in tests.

files_changed:
  - scraper/pipeline/extraction.py (strip_html preserves href, converts to inline [url] text)
  - scraper/pipeline/browser_scraper.py (added detail page enrichment: _is_sparse, _resolve_url, _merge_detail, _enrich_with_details, integrated into all 3 browser_scrape paths)
  - scraper/config.py (added BROWSER_DETAIL_MAX_PAGES setting)
  - scraper/tests/test_browser_scraper.py (added 17 new tests for all new functions)
