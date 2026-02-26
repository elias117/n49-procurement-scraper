# Phase 7 Context — BidsAndTenders Keyword Search

## Search Keyword Strategy

- **6 searches per portal** — one search per keyword category (Core Language/Translation, Official Languages/Bilingualism, Multilingual Coverage, Communications/Engagement, Procurement Vehicle Signals, plus the 6th category)
- **5 random keywords per batch** — randomly selected from each category on every scrape run, giving broader coverage over time
- **Both EN and FR keywords** in every search — a single search query includes both language versions (so up to 10 terms per search if 5 EN + 5 FR)
- **Categories with fewer than 5 keywords:** Use all available keywords for that category
- **Random selection re-rolls every run** — no persisted selection; each nightly run picks a fresh random 5 from each category

## OR Query Format & Fallback

- **Primary approach:** Combine keywords with OR operator in the search box (e.g., `translation OR traduction OR interpreter OR linguist`)
- **Fallback:** If OR-style query returns zero results, fall back to individual keyword searches for that batch (search each keyword separately)
- **Detection:** Zero results from an OR query triggers the fallback — assume the portal treats OR as literal text
- **Fallback scope:** Per-portal. If a portal doesn't support OR, all 6 batches for that portal use individual searches

## Search Result Handling

- **Search box is sufficient** — no post-extraction keyword filtering needed for BidsAndTenders portals
- **Deduplication is critical** — multiple keyword searches per portal will return overlapping listings; deduplicate by `source_listing_id` before upsert (reuse Phase 6 dedup logic)
- **Result aggregation:** Collect all listings from all 6 searches per portal into one list, deduplicate, then upsert
- **Pagination:** If search results span multiple pages, handle pagination (TBD by researcher/planner — depends on what the BidsAndTenders search UI does)

## Portal Search UI Edge Cases

- **All 29 portals share the same BidsAndTenders platform UI** — expect identical search behavior
- **Search box not found:** Log a warning and fall back to the current behavior (scrape all visible listings from `/Module/Tenders/en`, apply post-extraction keyword filter from Phase 6)
- **Search returns unexpected results:** Accept whatever the search returns — the search box is trusted as sufficient filtering
- **Best-effort approach:** If a portal is genuinely different, degrade gracefully rather than fail the entire run

## Architecture Notes

- Modifies `bidsandtenders_scrape()` in `scraper/pipeline/bidsandtenders.py`
- Keywords are already loaded by the orchestrator (Phase 6) — pass them into the scraper function
- Reuse `dedup_listings()` from Phase 6's keyword module
- No changes to database schema, API, or frontend
- Sequential portal processing remains (memory constraint unchanged)

## Deferred Ideas

(None raised during discussion)

---
*Created: 2026-02-25*
