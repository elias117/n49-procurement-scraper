---
status: complete
phase: 6-keyword-infrastructure
source: [6-01-SUMMARY.md, 6-02-SUMMARY.md, 6-03-SUMMARY.md]
started: 2026-02-25
updated: 2026-02-25
---

## Current Test

[testing complete]

## Tests

### 1. Keyword CSV Loading & Validation
expected: load_keywords() loads 120+ lowercased keywords from keywords_library.csv with 5 categories in EN/FR. Missing file, missing columns, or empty keywords raise SystemExit (fail-safe).
result: pass

### 2. Keyword Matching Edge Cases
expected: Case-insensitive substring match handles: case mismatch, partial matches, French accents (exact match and mismatch), multi-word phrases, None title/description, both None, empty strings, no match.
result: pass

### 3. Batch Filtering (filter_listings)
expected: filter_listings() keeps only keyword-matching listings, drops non-matching silently, preserves input order. 5 listings in → 3 matching out with correct IDs.
result: pass

### 4. Deduplication (deduplicate_listings)
expected: Removes duplicate source_listing_id entries keeping first occurrence. Listings with None source_listing_id are always kept. 5 in → 4 out.
result: pass

### 5. Orchestrator Integration Wiring
expected: run_pipeline() calls load_keywords() once before portal loop, passes keywords to each process_portal() call. filter_listings runs before dedup, dedup runs before validation. Purge runs after portal loop.
result: pass

### 6. Purge Function (purge_unmatched_listings)
expected: Fetches all listings from DB, applies same matches_keywords() function (PURG-02 consistency), batch-DELETEs non-matching rows in groups of 1000, logs result.
result: pass

### 7. Dockerfile Keywords CSV
expected: COPY keywords_library.csv ./keywords_library.csv is present in Dockerfile, placed after COPY scraper/ and before CMD. Resolves to /app/keywords_library.csv matching KEYWORDS_CSV_PATH.
result: pass

### 8. No Unwanted Dependencies
expected: scraper/pipeline/keywords.py imports only csv, logging, Path, Optional. No imports from scraper.db, orchestrator, or psycopg2. Pure-logic module.
result: pass

### 9. Full Test Suite Regression
expected: All scraper tests pass with no regressions after Phase 6 changes.
result: pass
notes: 121 tests passed (31 keyword + purge tests, 90 existing tests)

### 10. Requirements Coverage
expected: All 7 Phase 6 requirements (KWRD-01, KWRD-02, KWRD-03, FILT-01, FILT-05, PURG-01, PURG-02) are implemented and verified.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
