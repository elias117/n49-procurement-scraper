---
phase: 2-scraper-pipeline
plan: 01
subsystem: scraper-foundation
tags: [pydantic, postgresql, upsert, models, config, testing]
dependency_graph:
  requires: [db/migrations/001_initial_schema.sql]
  provides: [scraper/models.py, scraper/db.py, scraper/config.py, scraper/tests/]
  affects: [scraper/requirements.txt]
tech_stack:
  added: [pydantic-v2, psycopg2-binary, pytest, pytest-asyncio, instructor, browser-use, httpx, openai, beautifulsoup4, tenacity, tiktoken]
  patterns: [pydantic-models, parameterized-sql, upsert-on-conflict, context-manager-db, factory-function]
key_files:
  created:
    - scraper/__init__.py
    - scraper/config.py
    - scraper/models.py
    - scraper/db.py
    - scraper/pipeline/__init__.py
    - scraper/tests/__init__.py
    - scraper/tests/conftest.py
    - scraper/tests/test_models.py
    - scraper/tests/test_upsert.py
    - db/migrations/003_add_completeness_score.sql
    - pytest.ini
  modified:
    - scraper/requirements.txt
decisions:
  - Pydantic v2 BaseModel for all data models (matches schema exactly)
  - psycopg2 direct connections (no pool needed for sequential batch processing)
  - xmax=0 trick in RETURNING to distinguish new vs updated rows in upsert CTE
  - Embedding vectors passed as string format for pgvector compatibility
metrics:
  duration: 4m 30s
  completed: 2026-02-24T22:10:34Z
  tasks: 3/3
  tests: 24 passed
---

# Phase 2 Plan 01: Foundation Layer Summary

Pydantic data models, database upsert helpers, config module, and test infrastructure for the scraper pipeline -- all matching the PostgreSQL schema from Phase 1.

## What Was Built

### Task 1: Dependencies, Config, and Pydantic Models (28a5cb8)

**scraper/requirements.txt** -- Replaced Phase 1 stub with all Phase 2 dependencies: psycopg2-binary, pydantic, httpx, openai, instructor, browser-use, langchain-openai, beautifulsoup4, tenacity, tiktoken, pytest, pytest-asyncio.

**scraper/config.py** -- Environment-based configuration. DATABASE_URL and OPENAI_API_KEY are required (raise ValueError at import if missing). OPENAI_EMBEDDING_MODEL locked to text-embedding-3-small. Browser settings default to headless=False (POC finding: headless=True gets 403-blocked). Auto-disable threshold set to 5 consecutive failures.

**scraper/models.py** -- Five Pydantic models matching the DB schema:
- `ProcurementListing` -- LLM extraction target with instructor Field descriptions. classification_codes, value_min, value_max, and closing_date all include "NEVER guess or infer" instructions.
- `ExtractionResult` -- Wraps list of ProcurementListing for batch extraction.
- `ListingRecord` -- DB-ready record with portal metadata, embedding, completeness_score. No separate contact fields (consolidated into contact_info JSONB).
- `PortalRecord` -- Maps to portals table.
- `ScrapeRunRecord` -- Maps to scrape_runs table.
- `to_listing_record()` -- Factory function converting ProcurementListing to ListingRecord, consolidating contact_name/email/phone into contact_info JSONB dict (omits None keys).

**db/migrations/003_add_completeness_score.sql** -- Adds completeness_score NUMERIC column with index to listings table.

**pytest.ini** -- Configures pytest with testpaths, asyncio_mode=auto.

### Task 2: Database Helpers and Connection Management (797db95)

**scraper/db.py** -- Full database helper module:
- `get_connection()` / `db_connection()` context manager with commit/rollback/close.
- `get_enabled_portals(conn)` -- Returns list of PortalRecord for active portals.
- `get_portal_by_name(conn, name)` -- Single portal lookup.
- `disable_portal(conn, portal_id)` -- Sets enabled=false with timestamp.
- `check_auto_disable(conn, portal_id)` -- Queries last 5 runs, disables after 5 consecutive failures.
- `upsert_listings(conn, portal_id, listings)` -- CTE-based upsert with ON CONFLICT (source_portal, source_listing_id) DO UPDATE. Uses xmax=0 in RETURNING to count new vs updated. Revision counter increments. JSONB wrapped with psycopg2.extras.Json(). Embedding formatted as string for pgvector.
- `start_scrape_run()` / `complete_scrape_run()` / `fail_scrape_run()` -- Scrape run audit CRUD.
- All SQL uses %s parameterized queries, zero string interpolation.

### Task 3: Test Infrastructure and Unit Tests (d897832)

**scraper/tests/conftest.py** -- Shared fixtures: sample_listing_dict (full Canadian procurement data), sample_listing_minimal, sample_portal_dict, mock_db_connection, sample_html_content (3 listings in table), mock_openai_client.

**scraper/tests/test_models.py** -- 12 tests:
- ProcurementListing: all fields, minimal, rejects missing title, classification codes JSONB format
- ListingRecord: portal + embedding, null optional fields
- ExtractionResult: contains listings, empty valid
- PortalRecord: from dict
- to_listing_record: contact consolidation, omits None keys, null when all None

**scraper/tests/test_upsert.py** -- 12 tests:
- UPSERT SQL: contains ON CONFLICT, DO UPDATE, revision increment, last_scraped_at
- upsert_listings: empty list returns zeros, execute_values called with correct tuples
- Scrape runs: start inserts running, complete updates stats, fail sets error
- Auto-disable: triggers after 5 failures, does not trigger with 1 success, does not trigger with <5 runs

## Test Results

```
24 passed in 0.06s
```

All tests run with mocked DB connections, no external dependencies required.

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

1. `from scraper.models import ProcurementListing, ListingRecord, ExtractionResult` -- PASS
2. `from scraper.db import upsert_listings, get_enabled_portals` -- PASS
3. `from scraper.config import DATABASE_URL, OPENAI_API_KEY` raises ValueError without env vars -- PASS
4. `pytest scraper/tests/ -x -q` passes all 24 tests -- PASS
5. UPSERT SQL uses ON CONFLICT (source_portal, source_listing_id) DO UPDATE -- PASS
6. ProcurementListing field descriptions include "NEVER guess or infer" -- PASS

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| scraper/__init__.py | Created | Package init |
| scraper/config.py | Created | Environment config, logging |
| scraper/models.py | Created | 5 Pydantic models + factory function |
| scraper/db.py | Created | Connection, upsert, portal queries, scrape runs |
| scraper/pipeline/__init__.py | Created | Pipeline subpackage init |
| scraper/tests/__init__.py | Created | Tests package init |
| scraper/tests/conftest.py | Created | Shared test fixtures |
| scraper/tests/test_models.py | Created | 12 model validation tests |
| scraper/tests/test_upsert.py | Created | 12 upsert/DB logic tests |
| scraper/requirements.txt | Modified | All Phase 2 dependencies |
| db/migrations/003_add_completeness_score.sql | Created | Add completeness_score column |
| pytest.ini | Created | Test configuration |

## Commits

| Hash | Message |
|------|---------|
| 28a5cb8 | feat(2-01): add dependencies, config, Pydantic models, and project structure |
| 797db95 | feat(2-01): add database helpers with upsert, portal queries, and scrape run tracking |
| d897832 | test(2-01): add test infrastructure and unit tests for models and upsert |

## Self-Check: PASSED

- All 12 created files verified present on disk
- All 3 commit hashes (28a5cb8, 797db95, d897832) verified in git log
