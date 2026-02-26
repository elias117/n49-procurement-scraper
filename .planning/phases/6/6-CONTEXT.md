# Phase 6 Context — Keyword Infrastructure + CanadaBuys Filtering + Data Purge

## Keyword Matching Logic

- **Method:** Case-insensitive substring match (`keyword.lower() in text.lower()`)
- **Match targets:** Title AND description — a listing matches if ANY keyword hits in either field
- **Partial matches:** Allowed. "translation" matching "translator" or "mistranslation" is acceptable — false positives are negligible in procurement domain text
- **Multi-word keywords:** Matched as full phrases via substring (e.g., "services de traduction" matches as a contiguous string)
- **OR semantics:** A listing passes the filter if it matches at least one keyword from the full 122-keyword set (any category, any language)
- **No stemming or fuzzy matching** — simple substring is sufficient given the keyword list is curated

## Purge Behavior

- **Hard DELETE** — no soft delete, no tombstones
- **Scope:** All existing listings in the `listings` table that don't match any keyword on title or description
- **Same matching logic** as scraper filtering (PURG-02) — reuse the same function
- **No dry-run mode** — purge runs as part of the normal scrape job
- **Timing:** Purge runs once after CanadaBuys filtering is in place, as part of the scrape job

## Keyword Loading & Lifecycle

- **Load once** at the start of every scrape job
- **Fail-safe:** Scraper refuses to run if keywords CSV is missing, empty, or malformed — hard error, not a warning
- **Validation on load:** Confirm expected columns (Category, Language, Keyword), confirm non-zero keyword count
- **In-memory only:** Parsed into a list/set, no database table for keywords
- **File location:** `keywords_library.csv` in repo root (already exists, KWRD-02 satisfied)

## CanadaBuys Filtering Integration

- **Filter point:** After CSV parsing and field mapping into `ListingRecord` objects, before upsert
- **Non-matching listings are dropped silently** — they never reach the database
- **Observability:** Log total parsed count vs. matched count (e.g., "CanadaBuys: 4,230 listings parsed, 187 matched keywords")
- **No keyword-match metadata stored** on the listing — we don't track which keyword matched or how many matched

## Deduplication (FILT-05)

- **Scope:** Within a single scrape run, deduplicate by `source_listing_id` before upsert
- **For CanadaBuys:** Safety net only (single CSV download unlikely to have duplicates)
- **For future phases (7, 8):** Critical — multiple keyword searches will return overlapping results
- **Method:** Track seen `source_listing_id` values in a set; skip duplicates, keep first occurrence

## Architecture Notes

- Keyword loader is a standalone module usable by all three scraper strategies (CanadaBuys, BidsAndTenders, browser-use)
- Matching function is a single reusable utility: takes a listing's title+description and the keyword set, returns bool
- Purge reuses the same matching function against DB-fetched listings
- No changes to the database schema, API, or frontend

## Deferred Ideas

(None raised during discussion)

---
*Created: 2026-02-25*
