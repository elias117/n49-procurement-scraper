# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.
**Current focus:** v1.5 — Keyword-Filtered Scraping

## Current Position

Milestone: v1.5 — Keyword-Filtered Scraping
Phase: 7 (in progress)
Current Plan: 7-03
Status: 7-02 complete (3 tasks, 2 commits), 85 phase-7 tests passing, 160 scraper tests passing
Last activity: 2026-02-25 — Phase 7 Plan 2 executed (orchestrator wiring + search_used filter logic)

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

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 7-02-PLAN.md — next: execute 7-03-PLAN.md (if exists)
