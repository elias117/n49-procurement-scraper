# Roadmap: Procurement Intelligence Platform

## Completed Milestones

- [x] **v1.0** (2026-02-24) — 5 phases, 15 plans, 30 requirements. Full platform: scraper pipeline, hybrid search API, Next.js dashboard, nightly automation. [Archive](milestones/v1.0-ROADMAP.md)

## Current Milestone: v1.5 — Keyword-Filtered Scraping

**Goal:** The scraper only retrieves listings relevant to the BD team's translation/language services business, eliminating noise from irrelevant procurement categories.

**Keywords:** 122 keywords across 6 categories (Core Language/Translation, Official Languages/Bilingualism, Multilingual Coverage, Communications/Engagement, Procurement Vehicle Signals) in EN and FR.

### Phase 6: Keyword Infrastructure + CanadaBuys Filtering + Data Purge
**Goal:** The keyword loading module exists, CanadaBuys listings are filtered by keyword match on title/description, existing non-matching listings are purged, and deduplication logic is in place — ready for other scrapers to use.
**Requirements:** KWRD-01, KWRD-02, KWRD-03, FILT-01, FILT-05, PURG-01, PURG-02
**Plans:** 3 plans
Plans:
- [ ] 6-01-PLAN.md — Keyword module: load, match, filter, dedup functions + unit tests
- [ ] 6-02-PLAN.md — Orchestrator integration: wire keywords into pipeline + Dockerfile COPY
- [ ] 6-03-PLAN.md — Purge: delete non-matching listings from database + tests
**Success Criteria:**
  1. Keywords CSV is loaded and parsed correctly (122 keywords, 6 categories, 2 languages)
  2. CanadaBuys scraper filters listings — only keyword-matching listings are upserted
  3. Existing non-matching listings are purged from the database
  4. Deduplication removes duplicate source_listing_ids within a single scrape run
  5. Keyword matching is case-insensitive and works for both EN and FR terms
**Depends on:** v1.0 complete

### Phase 7: BidsAndTenders Keyword Search
**Goal:** All ~29 BidsAndTenders portals use the portal's search interface to query keywords via Playwright, returning only relevant listings.
**Requirements:** FILT-02, FILT-04
**Success Criteria:**
  1. Playwright types keywords into the BidsAndTenders search box and retrieves filtered results
  2. OR-style queries used where supported; curated core keywords where not
  3. Results from multiple keyword searches are deduplicated before upsert
  4. At least 3 BidsAndTenders portals return keyword-filtered listings successfully
**Depends on:** Phase 6 (keyword loader + dedup)

### Phase 8: Browser-Use Portals Keyword Search
**Goal:** Generic browser-use portals search for keywords using portal search forms instead of scraping all visible listings.
**Requirements:** FILT-03, FILT-04
**Success Criteria:**
  1. Agent prompt instructs the AI to use the portal's search form with keywords
  2. Curated keyword subset is used for portals with simple search boxes
  3. At least 3 browser-use portals return keyword-filtered listings successfully
  4. Portals without search forms fall back to post-extraction keyword filtering
**Depends on:** Phase 6 (keyword loader + dedup)

## Requirements Coverage

| Req | Phase | Description |
|-----|-------|-------------|
| KWRD-01 | 6 | Keyword CSV loading |
| KWRD-02 | 6 | Keywords file stored in repo |
| KWRD-03 | 6 | Case-insensitive EN/FR matching |
| FILT-01 | 6 | CanadaBuys client-side filtering |
| FILT-02 | 7 | BidsAndTenders search interface |
| FILT-03 | 8 | Browser-use agent search |
| FILT-04 | 7, 8 | Curated keyword subset for simple portals |
| FILT-05 | 6 | Deduplication within scrape runs |
| PURG-01 | 6 | Purge non-matching existing listings |
| PURG-02 | 6 | Purge uses same matching logic |

**Coverage:** 10/10 requirements mapped to phases.

---
*Last updated: 2026-02-25*
