# Requirements: Procurement Intelligence Platform

**Defined:** 2026-02-24
**Core Value:** The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Scraping & Extraction

- [x] **SCRP-01**: Scraper pipeline runs nightly against all 63 mapped Canadian government procurement portals
- [x] **SCRP-02**: AI-powered extraction produces structured fields per listing: title, description, posting date, closing date, source portal, classification codes (NAICS/UNSPSC/GSIN), category, region/province, estimated contract value, budget range, contact info, document/PDF links, amendment history
- [x] **SCRP-03**: Each scrape run logs per-portal results (success/fail, listing count, duration) to a scrape_runs audit table
- [x] **SCRP-04**: Post-extraction validation rejects listings with invalid data (closing_date < posting_date, values outside plausible range, missing required fields)
- [x] **SCRP-05**: Embeddings generated at insert time using text-embedding-3-small for every listing's title + description
- [x] **SCRP-06**: Listings upserted on (source_portal, source_listing_id) composite key to handle updates without duplicates

### Search & Filtering

- [x] **SRCH-01**: User can perform full-text keyword search across listing title and description
- [x] **SRCH-02**: User can filter listings by closing date range (default: open/future dates only)
- [x] **SRCH-03**: User can filter listings by region/province
- [x] **SRCH-04**: User can filter listings by source portal
- [x] **SRCH-05**: User can filter listings by posting date range
- [x] **SRCH-06**: User can filter listings by category/commodity code (NAICS, UNSPSC, GSIN)
- [x] **SRCH-07**: User can perform natural language search that finds semantically similar listings via pgvector
- [x] **SRCH-08**: Hybrid search combines keyword + semantic results via Reciprocal Rank Fusion for best-of-both ranking
- [x] **SRCH-09**: User can filter listings by estimated contract value range
- [x] **SRCH-10**: User can sort results by posting date, closing date, relevance score, or contract value

### Web Dashboard

- [x] **DASH-01**: User can view paginated listing results in a searchable table
- [x] **DASH-02**: User can click a listing to view full detail including all extracted fields
- [x] **DASH-03**: Listing detail includes a link to the original source portal page
- [x] **DASH-04**: User can log in with username and password (simple credentials auth)
- [x] **DASH-05**: Dashboard displays data freshness indicator showing when listings were last updated
- [x] **DASH-06**: Listings posted since the user's last visit are badged as "New"
- [x] **DASH-07**: User can view a scraper health page showing per-portal last-run status, success/fail, and listing count
- [x] **DASH-08**: Filter state is synced to the URL so searches are shareable via link
- [x] **DASH-09**: Listing detail displays document attachment links and contact information when available

### Infrastructure

- [x] **INFR-01**: All services run via Docker Compose on a single EC2 instance
- [x] **INFR-02**: PostgreSQL 17 with pgvector serves as the single data store for structured data and vector embeddings
- [x] **INFR-03**: AWS infrastructure provisioned via Terraform in ca-central-1
- [x] **INFR-04**: Nginx handles TLS termination and reverse proxying to application services
- [ ] **INFR-05**: Automated nightly scheduling triggers scraper pipeline at 2 AM ET

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Notifications

- **NOTF-01**: User receives email alerts for new listings matching saved search criteria
- **NOTF-02**: User can configure alert frequency (immediate, daily digest)

### Advanced Features

- **ADVN-01**: User can save search profiles for quick re-use
- **ADVN-02**: User can bookmark/flag individual listings for follow-up
- **ADVN-03**: Amendment history tracking shows changes to listings over time
- **ADVN-04**: Cross-portal deduplication identifies and merges duplicate listings from different portals

### Monitoring

- **MNTR-01**: Dead-man alert fires if no new listings appear in 26+ hours
- **MNTR-02**: CloudWatch alarm fires if EC2 memory exceeds 80%
- **MNTR-03**: Per-portal yield alerting when a previously-active portal returns 0 listings

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| CRM / pipeline management | Scope creep — this is a search tool, not a CRM |
| Bid scoring / AI recommendations | Complex ML feature; validate basic search adoption first |
| Proposal writing assistance | Different product entirely |
| OAuth / SSO / RBAC | Simple auth sufficient for small internal team (PROJECT.md) |
| Real-time scraping | Nightly batch sufficient for procurement cadence (PROJECT.md) |
| Mobile app | Web dashboard only (PROJECT.md) |
| Multi-tenant SaaS features | Internal tool, single team (PROJECT.md) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCRP-01 | Phase 2 | Complete (2-04) |
| SCRP-02 | Phase 2 | Complete (2-03) |
| SCRP-03 | Phase 2 | Complete (2-04) |
| SCRP-04 | Phase 2 | Complete (2-02) |
| SCRP-05 | Phase 2 | Complete (2-02) |
| SCRP-06 | Phase 2 | Complete (2-01 upsert + 2-04 orchestrator) |
| SRCH-01 | Phase 3 | Complete |
| SRCH-02 | Phase 3 | Complete |
| SRCH-03 | Phase 3 | Complete |
| SRCH-04 | Phase 3 | Complete |
| SRCH-05 | Phase 3 | Complete |
| SRCH-06 | Phase 3 | Complete |
| SRCH-07 | Phase 3 | Complete |
| SRCH-08 | Phase 3 | Complete |
| SRCH-09 | Phase 3 | Complete |
| SRCH-10 | Phase 3 | Complete |
| DASH-01 | Phase 4 | Complete (4-02) |
| DASH-02 | Phase 4 | Complete (4-03) |
| DASH-03 | Phase 4 | Complete (4-03) |
| DASH-04 | Phase 4 | Complete (4-01) |
| DASH-05 | Phase 4 | Complete (4-03) |
| DASH-06 | Phase 4 | Complete (4-03) |
| DASH-07 | Phase 4 | Complete (4-04) |
| DASH-08 | Phase 4 | Complete (4-02) |
| DASH-09 | Phase 4 | Complete (4-03) |
| INFR-01 | Phase 1 | Complete (1-01) |
| INFR-02 | Phase 1 | Complete (1-01) |
| INFR-03 | Phase 1 | Complete (1-01) |
| INFR-04 | Phase 1 | Complete (1-01) |
| INFR-05 | Phase 5 | In progress (5-01 infra ready, 5-02 crontab pending) |

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after roadmap creation (all 30 requirements mapped)*
