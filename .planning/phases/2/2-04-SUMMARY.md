---
phase: 2-scraper-pipeline
plan: 04
subsystem: orchestrator-audit-cli
tags: [orchestrator, audit, cli, argparse, xvfb, error-isolation]
dependency_graph:
  requires: [2-01, 2-02, 2-03]
  provides: [run_pipeline, scrape_portal, process_portal, start_run, complete_run, fail_run, main-cli]
  affects: [scraper/Dockerfile]
tech_stack:
  added: [argparse, xvfb-run]
  patterns: [per-portal-error-isolation, sequential-processing, portal-dispatch, audit-wrappers]
key_files:
  created:
    - scraper/pipeline/audit.py
    - scraper/pipeline/orchestrator.py
    - scraper/tests/test_audit.py
    - scraper/tests/test_orchestrator.py
  modified:
    - scraper/main.py
    - scraper/Dockerfile
decisions:
  - Per-portal error isolation with try/except in process_portal (failed portal returns error dict, pipeline continues)
  - Sequential portal processing for 4GB memory constraint (no async.gather)
  - sys.path fix in main.py for Docker CMD direct invocation compatibility
  - classify_portal uses name match for CanadaBuys, URL match for BidsAndTenders, fallback to browser
metrics:
  duration: 195s
  completed: 2026-02-24T22:26:08Z
  tasks: 2/3 (Task 3 is human-verify checkpoint)
  tests_added: 22
  tests_total: 90
---

# Phase 2 Plan 04: Orchestrator, Audit & CLI Summary

Pipeline orchestrator tying all modules together with three-path portal dispatch, per-portal error isolation, audit logging wrappers, and argparse CLI replacing the Phase 1 sleep stub. Dockerfile updated with xvfb for non-headless Chromium.

## What Was Built

### Task 1: Audit Logging and Orchestrator (a95e779)

**`scraper/pipeline/audit.py`** -- Thin wrappers around db.py scrape run functions:
- `start_run(conn, portal)` -- Calls db.start_scrape_run, logs portal name and URL
- `complete_run(conn, run_id, portal, stats)` -- Calls db.complete_scrape_run, logs found/new/updated counts
- `fail_run(conn, run_id, portal, error)` -- Calls db.fail_scrape_run, logs error, checks auto-disable and logs warning if triggered

**`scraper/pipeline/orchestrator.py`** -- Main pipeline loop:
- `classify_portal(portal)` -- Dispatches: "canadabuys" (name match), "bidsandtenders" (URL match), "browser" (fallback)
- `scrape_portal(portal)` -- Routes to canadabuys_ingest, bidsandtenders_scrape, or browser_scrape
- `process_portal(conn, portal)` -- Full pipeline for ONE portal: scrape -> convert ProcurementListing to ListingRecord -> validate_and_score (skip ValueError) -> generate_embeddings -> upsert_listings -> audit. Catches ALL exceptions for per-portal error isolation
- `run_pipeline(portal_name=None)` -- Sequential processing of all enabled portals (or single portal). Logs summary totals at end

**`scraper/tests/test_audit.py`** -- 7 tests: start_run DB call, return run_id, complete_run DB call and logging, fail_run DB call and auto-disable check and disable logging

**`scraper/tests/test_orchestrator.py`** -- 15 tests: classify_portal dispatch (4 tests), scrape_portal dispatch (3 tests), process_portal error isolation + flow order + ProcurementListing conversion + skip invalid listings (4 tests), run_pipeline all enabled + single portal + unknown portal raises + error isolation (4 tests)

### Task 2: CLI Entrypoint and Dockerfile Update (f55f47a)

**`scraper/main.py`** -- Real CLI replacing Phase 1 sleep stub:
- argparse with `--portal` (run single portal) and `--list-portals` (show all portals)
- `asyncio.run(run_pipeline(...))` as the execution path
- Pipeline summary printed at end: portals processed, listings found/new/updated, errors, duration
- Exit code 1 only if ALL portals fail
- sys.path fix for Docker CMD compatibility (running `python main.py` from within scraper/ dir)

**`scraper/Dockerfile`** -- Updated for Phase 2:
- Added `apt-get install -y xvfb` for virtual framebuffer
- Added explicit `playwright install chromium`
- CMD changed to `xvfb-run --auto-servernum --server-args=-screen 0 1920x1080x24 python main.py`
- Scraper now runs once and exits (not the Phase 1 sleep loop)

### Task 3: Live Benchmark (PENDING)

Task 3 is a `checkpoint:human-verify` gate requiring user to run the pipeline against 5 representative portals with a real database and OpenAI API key. This verifies end-to-end functionality and measures real-world LLM cost before enabling all 63 portals.

## Test Results

```
90 passed in 2.51s
```

- Plan 2-01 tests: 24 (models + upsert)
- Plan 2-02 tests: 34 (validation + canadabuys + embeddings)
- Plan 2-03 tests: 10 (extraction)
- Plan 2-04 tests: 22 (audit + orchestrator)

All tests run with mocked dependencies, no external services required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sys.path fix for direct file invocation**
- **Found during:** Task 2, CLI verification
- **Issue:** Running `python scraper/main.py --help` or `python main.py` from the scraper/ directory fails with ModuleNotFoundError because the parent directory is not on sys.path
- **Fix:** Added sys.path.insert(0, parent_dir) at the top of main.py to ensure `scraper` package is importable regardless of invocation method
- **Files modified:** scraper/main.py
- **Commit:** f55f47a

## Verification Results

1. `python3 -m pytest scraper/tests/ -x -q` -- 90 passed
2. `python3 scraper/main.py --help` -- Shows --portal and --list-portals flags
3. `from scraper.main import main` -- Imports successfully
4. `from scraper.pipeline.orchestrator import run_pipeline, scrape_portal` -- Imports successfully
5. `from scraper.pipeline.audit import start_run, complete_run, fail_run` -- Imports successfully

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| scraper/pipeline/audit.py | Created | Scrape run audit logging wrappers |
| scraper/pipeline/orchestrator.py | Created | Pipeline orchestrator with dispatch and error isolation |
| scraper/tests/test_audit.py | Created | 7 audit logging tests |
| scraper/tests/test_orchestrator.py | Created | 15 orchestrator tests |
| scraper/main.py | Modified | Real CLI replacing Phase 1 sleep stub |
| scraper/Dockerfile | Modified | Xvfb, chromium, xvfb-run CMD |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | a95e779 | feat(2-04): add audit logging and pipeline orchestrator |
| 2 | f55f47a | feat(2-04): add CLI entrypoint and update Dockerfile for xvfb |

## Self-Check: PASSED

- All 5 created files verified present on disk
- All 2 modified files verified present on disk
- Both task commits (a95e779, f55f47a) verified in git log
- 90 tests passing across all 4 plans
