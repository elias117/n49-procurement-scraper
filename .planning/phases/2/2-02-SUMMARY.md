---
phase: 2-scraper-pipeline
plan: 02
subsystem: validation-ingestion-embeddings
tags: [validation, csv-ingestion, embeddings, canadabuys, openai, tiktoken]

dependency_graph:
  requires: [2-01]
  provides: [validate_listing, compute_completeness_score, canadabuys_ingest, generate_embeddings]
  affects: [2-03, 2-04]

tech_stack:
  added: [tiktoken, tenacity, httpx]
  patterns: [field-nullification-over-rejection, deterministic-hash-fallback, utf8-sig-bom-handling, token-aware-batching]

key_files:
  created:
    - scraper/pipeline/validation.py
    - scraper/pipeline/canadabuys.py
    - scraper/pipeline/embeddings.py
    - scraper/tests/test_validation.py
    - scraper/tests/test_canadabuys.py
    - scraper/tests/test_embeddings.py
  modified: []

decisions:
  - BOM stripping added defensively in _parse_csv as well as in httpx utf-8-sig decoding
  - Retry decorator uses broad Exception type for simplicity; can narrow to openai-specific errors when library imported
  - Lazy tiktoken encoder initialization to avoid import-time overhead

metrics:
  duration: 343s
  completed: 2026-02-24T22:19:02Z
  tests_added: 34
  tests_total: 68
  files_created: 6
---

# Phase 2 Plan 02: Validation, CSV Ingestion & Embeddings Summary

Post-extraction validation layer that nullifies bad fields (never rejects), CanadaBuys CSV zero-cost ingestion via httpx + csv.DictReader with utf-8-sig BOM handling, and OpenAI embedding generation with token-aware batch splitting under 250K limit using tiktoken cl100k_base.

## What Was Built

### Task 1: Post-extraction Validation and Completeness Scoring
**Files:** `scraper/pipeline/validation.py`, `scraper/tests/test_validation.py`

- `validate_listing()` applies 8 validation rules that nullify bad fields without rejecting listings
- Only rejection case: missing title raises ValueError
- `source_listing_id` fallback: generates deterministic SHA-256 hash from `{portal}:{title}:{url}` when missing
- Closing date before posting date -> null. Values outside 0-10B -> null. Invalid status -> "open"
- Classification codes missing system/code keys are removed
- `compute_completeness_score()` scores 9 fields on a 0.0-1.0 scale
- `validate_and_score()` convenience function combines both
- **16 tests** covering all validation rules, fallback ID generation, and completeness scoring

### Task 2: CanadaBuys CSV Ingestion Handler
**Files:** `scraper/pipeline/canadabuys.py`, `scraper/tests/test_canadabuys.py`

- `canadabuys_ingest()` downloads CSV via httpx.AsyncClient with 120s timeout
- Decodes with `utf-8-sig` to handle BOM; also strips BOM defensively in `_parse_csv()`
- `_parse_csv()` extracted for testability (no HTTP calls needed in tests)
- Full CANADABUYS_FIELD_MAP from research with 25+ column mappings
- English preferred with French fallback for bilingual fields (title, description, URL)
- Builds classification codes from GSIN and UNSPSC fields
- Builds contact_info JSONB from name/email/phone fields
- Rows missing referenceNumber are skipped
- **10 tests** covering field mapping, language fallback, BOM handling, and edge cases

### Task 3: Embedding Generation with Batch Processing
**Files:** `scraper/pipeline/embeddings.py`, `scraper/tests/test_embeddings.py`

- `generate_embeddings()` processes listings in batches respecting 250K token limit and 2048 items per request
- Uses tiktoken `cl100k_base` encoding for accurate token counting
- Truncates text at 8000 tokens (margin below 8192 API limit)
- Tenacity retry decorator: 3 attempts with exponential backoff (1-30s)
- Embedding text format: "Title\n\nDescription" (handles None description)
- Sets `listing.embedding` (1536-dim vector) and `listing.embedding_model` on each record
- **8 tests** with mocked OpenAI client covering API calls, batching, truncation

## Test Results

```
68 passed in 2.46s
```

- Plan 2-01 tests: 24 (unchanged, still passing)
- Plan 2-02 tests: 34 new (16 validation + 10 canadabuys + 8 embeddings)
- All imports verified: validation, canadabuys, embeddings

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BOM handling in _parse_csv**
- **Found during:** Task 2, test_utf8_bom_handled failure
- **Issue:** When BOM character (\ufeff) is present in the CSV text string passed directly to _parse_csv, it attaches to the first column header name, causing csv.DictReader to fail key lookups for referenceNumber
- **Fix:** Added BOM stripping at the start of _parse_csv in addition to the utf-8-sig decoding in canadabuys_ingest
- **Files modified:** scraper/pipeline/canadabuys.py
- **Commit:** 2690710

**2. [Rule 1 - Bug] Adjusted batch splitting test parameters**
- **Found during:** Task 3, test_batch_splitting_respects_token_limit failure
- **Issue:** Test used 10 listings * ~7500 tokens = ~75K total tokens, but texts get truncated to 8000 tokens max, so 10 * 8K = 80K was under 250K limit
- **Fix:** Increased to 35 listings * ~8000 tokens each = ~280K > 250K limit to actually trigger batch splitting
- **Files modified:** scraper/tests/test_embeddings.py
- **Commit:** 3c2fc8d

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | c1f843f | feat(2-02): add post-extraction validation and completeness scoring |
| 2 | 2690710 | feat(2-02): add CanadaBuys CSV ingestion handler |
| 3 | 3c2fc8d | feat(2-02): add embedding generation with batch processing |

## Self-Check: PASSED

All 7 files exist. All 3 commit hashes verified in git log.
