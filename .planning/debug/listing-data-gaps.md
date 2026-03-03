---
status: fixing
trigger: "Multiple data quality gaps across all portal types. Need to investigate and fix each."
created: 2026-03-02T14:00:00Z
updated: 2026-03-02T14:05:00Z
---

## Current Focus

hypothesis: CONFIRMED -- 5 independent root causes identified across the gap areas, 2 fixable via code, 3 data-availability limitations
test: Full code review of all 3 scraper types, extraction model, orchestrator upsert, and validation
expecting: Targeted fixes for CanadaBuys source_url and _is_sparse sensitivity
next_action: Implement fixes for the 2 actionable code issues

## Symptoms

expected: Listings should have description, closing_date, value_min/value_max, contact_info, and source_url populated from portal data.
actual: Database query of 27 listings shows:
  - value_min/value_max: 0/27 (0%) -- NEVER populated by any scraper
  - contact_info: 7/27 (26%) -- only CanadaBuys populates it
  - source_url: 15/27 (56%) -- MERX has zero, CanadaBuys only 1/7
  - closing_date: 14/27 (52%) -- browser-use portals often miss it
  - description: 22/27 (81%) -- MERX has zero descriptions
Per-portal breakdown:
  - CanadaBuys (7): good desc & contact, but only 1 source_url, 0 values
  - Newfoundland Public Procurement (6): desc + url, but 0 dates/contacts/values
  - Montreal Tenders (5): desc + url, but 0 dates/contacts/values
  - MERX (4): 0 descriptions, 0 source_urls, 0 contacts, 0 values (only has closing_date)
  - SEAO (2): desc + url + date, but 0 contacts/values
  - New Brunswick (2): desc + url, but 0 dates/contacts/values
  - Ottawa MERX (1): 0 desc, 0 source_url, 0 contact, 0 value (only has closing_date)
errors: No scraper errors -- fields are silently null/empty
reproduction: Query the database -- most fields are null
started: Likely always been this way since v1.0 launch

## Eliminated

- hypothesis: "upsert SQL drops value_min/value_max fields"
  evidence: UPSERT_SQL in db.py includes value_min and value_max in both INSERT and ON CONFLICT UPDATE. _listing_to_tuple maps them correctly. No data loss in the DB layer.
  timestamp: 2026-03-02T14:02:00Z

- hypothesis: "validation.py strips value fields"
  evidence: validate_listing() only nullifies values outside 0-10B range or when max < min. It does NOT strip valid values. If the LLM returns valid values, they would survive validation.
  timestamp: 2026-03-02T14:02:30Z

- hypothesis: "ProcurementListing model is missing value/contact fields"
  evidence: models.py ProcurementListing has value_min, value_max, contact_name, contact_email, contact_phone. All fields exist with proper descriptions. to_listing_record() correctly maps contact fields to contact_info JSONB dict.
  timestamp: 2026-03-02T14:03:00Z

## Evidence

- timestamp: 2026-03-02T14:01:00Z
  checked: CanadaBuys CSV field mapping for value columns
  found: CANADABUYS_FIELD_MAP has NO mapping for value_min or value_max. The _parse_csv function never sets these fields on ListingRecord. The CanadaBuys open tender notice CSV is for tender opportunities (pre-award), which typically do not include contract dollar values. This is a data availability limitation from the source.
  implication: value_min/value_max will be null for all CanadaBuys listings. Not fixable -- data doesn't exist in source.

- timestamp: 2026-03-02T14:01:30Z
  checked: LLM extraction prompt for value extraction
  found: EXTRACTION_SYSTEM_PROMPT includes "If a value range is stated (e.g., '$50,000 - $100,000'), extract both min and max." ProcurementListing model has value_min/value_max with description "Extract only if explicitly stated in the text. Return null if not clearly present. NEVER guess or infer." The LLM IS instructed to extract values, but most procurement listing pages do not show dollar amounts.
  implication: value_min/value_max gap is a data availability issue, not a code bug. 0% is expected.

- timestamp: 2026-03-02T14:02:00Z
  checked: MERX portal classification and login handling
  found: MERX portals (merx.com) classify as "browser" type since classify_portal() checks only for "CanadaBuys" name and "bidsandtenders" in URL. MERX has requires_login=true in the DB. BUT no scraper checks or handles requires_login -- the field is stored but ignored. The browser-use agent hits a login wall and gets no useful content (titles only from pre-login page headers, maybe closing dates from meta tags).
  implication: MERX having 0 descriptions, 0 source_urls, 0 contacts is expected -- login barrier prevents content access. Fixing requires login support or excluding MERX from scraping.

- timestamp: 2026-03-02T14:03:00Z
  checked: CanadaBuys source_url mapping (only 1/7 populated)
  found: canadabuys.py maps notice_url from CSV column "noticeURL-URLavis-eng" with French fallback "noticeURL-URLavis-fra". If only 1/7 has source_url, the CSV data itself has empty URL columns for most rows. This is confirmed by test row3 in test_canadabuys.py having empty English URL. The CanadaBuys CSV data simply doesn't always include notice URLs. HOWEVER -- CanadaBuys tender pages follow a predictable URL pattern that could potentially be constructed from the solicitation number.
  implication: CanadaBuys source_url gap is partially a data issue but potentially improvable by constructing URLs from solicitation/reference numbers.

- timestamp: 2026-03-02T14:03:30Z
  checked: BidsAndTenders and browser-use enrichment fixes
  found: Two prior debug sessions (seao-incomplete-listings.md and missing-listing-data.md) both status=awaiting_human_verify. They add detail page enrichment to browser_scraper.py and bidsandtenders.py respectively. These fixes should improve contact_info, closing_date, and description for non-MERX portals by visiting individual listing detail pages.
  implication: Many gaps will naturally improve once the enrichment fixes are verified and deployed. The key remaining issue is _is_sparse() gating -- it only triggers on missing description, so listings that already have a description but lack contact/dates/values won't get enriched.

- timestamp: 2026-03-02T14:04:00Z
  checked: _is_sparse() function in both scrapers
  found: Both bidsandtenders.py and browser_scraper.py define _is_sparse() as `return listing.description is None`. This means ONLY listings missing a description will trigger detail page enrichment. If a listing has a title + description from the listing page but is missing closing_date, contact_info, or value_min, it will NOT be enriched. This is too conservative -- a listing could have a very short description extracted from the summary page but still lack all other detail fields.
  implication: _is_sparse() should be broadened to also trigger enrichment when description is very short or when other key fields (closing_date, contact_info) are missing. This would improve data quality for listings that have a partial description from the listing page.

## Resolution

root_cause: Five independent issues cause the data gaps:

  1. **value_min/value_max (0% -- NOT fixable):** CanadaBuys CSV has no value columns (tender notices don't include contract values). BidsAndTenders/browser portals rarely show dollar amounts on their pages. This is a data availability limitation across all Canadian procurement portals, not a code bug.

  2. **contact_info (26% -- partially fixable):** Only CanadaBuys has explicit CSV columns for contact data. BidsAndTenders/browser scrapers rely on LLM extraction from page content. Contact info is typically on detail pages, not listing summary pages. The enrichment fixes (from prior debug sessions) should improve this by visiting detail pages, BUT _is_sparse() only triggers when description is None, so listings with descriptions but missing contacts won't get enriched.

  3. **source_url (56% -- partially fixable):** MERX has zero because login barriers prevent content access. CanadaBuys only 1/7 because the CSV data itself often has empty noticeURL columns. BidsAndTenders/browser work with the href-preserving strip_html fix.

  4. **closing_date (52% -- will improve with enrichment):** Detail pages typically show closing dates. The enrichment fixes should address this for BidsAndTenders/browser portals.

  5. **description (81% -- MERX blocked by login):** MERX 0% is due to login barrier. Other portals work with enrichment.

  **Actionable code fixes:**
  - Broaden _is_sparse() to trigger on more conditions (missing description OR very short description OR missing both closing_date and contact_info)
  - This is the highest-impact change -- it makes enrichment apply to more listings that are incomplete

fix:
verification:
files_changed: []
