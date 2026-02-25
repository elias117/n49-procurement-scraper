# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.
**Current focus:** v1.5 — Keyword-Filtered Scraping

## Current Position

Milestone: v1.5 — Keyword-Filtered Scraping
Phase: 8 (complete)
Current Plan: 8-02 (done)
Status: 8-02 complete (4 tasks, 3 commits), 25 orchestrator tests passing, 145 scraper tests passing
Last activity: 2026-02-25 — Phase 8 Plan 2 executed (orchestrator wiring for browser keyword search)

## Milestone History

| Milestone | Phases | Plans | Requirements | Completed |
|-----------|--------|-------|--------------|-----------|
| v1.0 | 5 | 15 | 30/30 | 2026-02-24 |

## Performance Metrics (v1.0)

**Velocity:**
- Total plans completed: 15
- Average duration: ~4.6 min
- Total execution time: ~69 min

## Accumulated Context

### Tech Debt
- reference_number column missing (scraper extracts, DB doesn't persist)
- robots.txt compliance audit deferred

### v2 Candidates (Deferred)
- Email alerts / saved search notifications (NOTF-01, NOTF-02)
- Saved search profiles (ADVN-01)
- Bookmark/flag listings (ADVN-02)
- Amendment history tracking (ADVN-03)
- Cross-portal deduplication (ADVN-04)
- CloudWatch monitoring (MNTR-01, MNTR-02, MNTR-03)

### v1.5 Key Context
- Keywords CSV: 122 keywords, 5 categories, EN + FR
- Categories: Core Language/Translation, Official Languages/Bilingualism, Multilingual Coverage, Communications/Engagement, Procurement Vehicle Signals
- CanadaBuys: filter client-side after CSV download (no API switch needed)
- BidsAndTenders: ~29 portals share identical UI, use Playwright search box
- Browser-use: ~13 enabled portals, modify agent prompt to search for keywords
- Purge: DELETE existing listings not matching any keyword

### Decisions
- Module-level playwright import with try/except for testability
- Re-find search input after each reset (page reloads may invalidate locators)
- BidsAndTendersResult NamedTuple signals orchestrator whether post-filter is needed
- search_used flag drives conditional filtering: True=skip filter, False=apply filter (handles search-box-not-found fallback)
- `from __future__ import annotations` for Python 3.9 compat in orchestrator (matches bidsandtenders.py)
- BrowserScrapeResult NamedTuple mirrors BidsAndTendersResult pattern for consistent search_used signaling
- _detect_search_used checks action_names() for "input_text" -- definitive signal of search form interaction
- OR fallback persists across categories (once portal rejects OR, all subsequent use single keywords)
- BROWSER_SEARCH_MAX_STEPS (default 50) controls global step budget across category searches
- browser_scrape now receives keywords_by_category, consistent with bidsandtenders_scrape pattern
- BrowserScrapeResult unpacked identically to BidsAndTendersResult in orchestrator dispatch

## Quick Tasks Completed

| Task | Date | Commits | Description |
|------|------|---------|-------------|
| QT-001 | 2026-02-25 | b11b979 | Fix portal filter 500 error — query builder was casting portal names as UUIDs |
| QT-002 | 2026-02-25 | ff451c1 | Fix date display off-by-one — add timeZone: "UTC" to formatDate() |

## Session Continuity

Last session: 2026-02-25
Stopped at: Fixed portal filter 500 (QT-001) and date timezone display (QT-002). DB diagnosis confirmed dates are correct — 897 listings, 219 distinct posting dates, 0 with posting==closing. User likely saw many CanadaBuys batch-published listings sharing the same posting date.
