# Procurement Scraper Roadmap

## Goal
Move from portal-by-portal scraping to family-based ETL scrapers, where each platform family has one reusable scraper.

## Phase 1: BidsAndTenders (29 portals)
- Refactor `pipeline/bidsandtenders.py` to direct listing scrape.
- Load `{tenant}/Module/Tenders/en` and collect all active tenders.
- Remove keyword-search scraping behavior.
- Handle pagination and normalize listing URLs.

## Phase 2: SEAO - Quebec (9 portals)
- Add `pipeline/seao.py` for `https://seao.gouv.qc.ca`.
- Scrape active tenders from:
  - `https://seao.gouv.qc.ca/avis-resultat-recherche?statIds=6&tpIds=2%2C3%2C5%2C6%2C7%2C8%2C10%2C14%2C15%2C17%2C18%2C19`
- Parse paginated structured table into listings.
- Route SEAO portals in orchestrator.

## Phase 3: MERX (5 portals)
- Add family scraper for `https://www.merx.com/{tenant}`.
- Standardize extraction across MERX tenants.
- Handle tenant-specific subpaths with shared parser logic.

## Phase 4: Tier 3 Cities (individual scrapers)
- Build individual scrapers for custom HTML portals.
- Start with Windsor (`https://opendata.citywindsor.ca/Tools/BidsAndTenders`) because DataTables exposes all rows in DOM on load.
- Then implement Vancouver, Montreal, Cambridge, Coquitlam, Kelowna, Kingston, Newfoundland PPA, Quebec City.

## Phase 5: SAP Ariba Public Listings
- Add dedicated public-listing scrapers for:
  - Edmonton
  - Toronto
  - Nova Scotia
- Normalize output to existing `ProcurementListing` model.

## Phase 6: Secondary Platforms
- Add platform scrapers for:
  - APC
  - SaskTenders
  - BC Bid
  - NBON
- Prioritize reusable selectors/parsers by platform style.

## Phase 7: Monitoring and Health
- Add run monitoring and alerting.
- Build per-portal health dashboard:
  - scrape success rate
  - listing volume deltas
  - extraction error rate
  - stale portal detection
- Add automated regression checks for family scrapers.
