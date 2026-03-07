# Portal Families

## Family 1: BidsAndTenders (29 portals)
- Pattern: `https://{tenant}.bidsandtenders.ca/Module/Tenders/en`
- Scraper: `pipeline/bidsandtenders.py`
- Approach:
  - One scraper for all tenants.
  - Load tenant listing page and collect all active tenders.
  - No keyword search.
  - Handle pagination and detail URL normalization.

## Family 2: SEAO - Quebec (9 portals)
- Platform: `https://seao.gouv.qc.ca`
- Active tenders URL:
  - `https://seao.gouv.qc.ca/avis-resultat-recherche?statIds=6&tpIds=2%2C3%2C5%2C6%2C7%2C8%2C10%2C14%2C15%2C17%2C18%2C19`
- Results path: `https://seao.gouv.qc.ca/avis-resultat-recherche`
- Scraper: `pipeline/seao.py`
- Approach:
  - One scraper for all SEAO-backed portals.
  - Parse structured paginated table for title, reference number, organization, category, open date, close date, and detail URL.

## Family 3: MERX (5 portals)
- Pattern: `https://www.merx.com/{tenant}`
- Example tenants:
  - `/govnl`
  - `/cityofottawa`
  - `/mbgov`
- Scraper approach:
  - One family scraper with tenant-specific base path.
  - Shared extraction logic across MERX tenants.

## Family 4: CanadaBuys (1 portal)
- URL: `https://canadabuys.canada.ca`
- Scraper: `pipeline/canadabuys.py`
- Approach:
  - RSS/feed ingestion.
  - Keep existing working implementation unchanged.

## Family 5: Tier 3 - Custom HTML (9 portals)
- Portals:
  - Windsor: `https://opendata.citywindsor.ca/Tools/BidsAndTenders`
  - Vancouver: `https://bids.vancouver.ca/`
  - Montreal: `https://montreal.ca/en/services/tenders-and-contracts`
  - Cambridge
  - Coquitlam
  - Kelowna
  - Kingston
  - Newfoundland PPA
  - Quebec City
- Scraper approach:
  - Individual scraper per portal.
  - Windsor first (DataTables with all listings in DOM on load).
