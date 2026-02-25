# v1.5 Requirements — Keyword-Filtered Scraping

**Milestone:** v1.5
**Defined:** 2026-02-25
**Core Value:** The scraper only retrieves listings relevant to the BD team's translation/language services business, eliminating noise from irrelevant procurement categories.

## Keyword Infrastructure (3)

- [ ] **KWRD-01**: Keywords loaded from CSV file (Category, Language, Keyword columns) at scraper startup and made available to all scraper strategies
- [ ] **KWRD-02**: Keywords CSV stored in the repository at a known path for reference
- [ ] **KWRD-03**: Keyword matching is case-insensitive and supports both EN and FR keywords

## Scraper Filtering (5)

- [ ] **FILT-01**: CanadaBuys CSV listings filtered client-side by keyword match on title and description before upsert
- [x] **FILT-02**: BidsAndTenders Playwright scraper uses portal search interface to query keywords, using OR-style queries where supported
- [ ] **FILT-03**: Browser-use agent prompt updated to search for keywords using portal search forms instead of browsing all listings
- [ ] **FILT-04**: For portals with simple search boxes (no OR support), a curated subset of core translation keywords is used
- [ ] **FILT-05**: Listings from multiple keyword searches within a run are deduplicated by source_listing_id before upsert

## Data Cleanup (2)

- [ ] **PURG-01**: Existing listings not matching any keyword are purged from the database
- [ ] **PURG-02**: Purge uses the same keyword-matching logic as the scraper filters for consistency

## Summary

- Total requirements: 10
- Keyword Infrastructure: 3
- Scraper Filtering: 5
- Data Cleanup: 2

## Deferred (v2 Candidates)

- Email alerts / saved search notifications (NOTF-01, NOTF-02)
- Saved search profiles (ADVN-01)
- Bookmark/flag listings (ADVN-02)
- Amendment history tracking (ADVN-03)
- Cross-portal deduplication (ADVN-04)
- CloudWatch monitoring (MNTR-01, MNTR-02, MNTR-03)
- reference_number persistence (DEBT-01)
- robots.txt compliance audit (DEBT-02)

---
*Defined: 2026-02-25*
