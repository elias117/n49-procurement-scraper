---
phase: 2-scraper-pipeline
plan: 04
type: execute
wave: 3
depends_on: ["2-01", "2-02", "2-03"]
files_modified:
  - scraper/pipeline/audit.py
  - scraper/pipeline/orchestrator.py
  - scraper/main.py
  - scraper/Dockerfile
  - scraper/tests/test_audit.py
  - scraper/tests/test_orchestrator.py
autonomous: false
requirements:
  - SCRP-01
  - SCRP-03

must_haves:
  truths:
    - "Running python main.py scrapes all enabled portals sequentially and populates listings in PostgreSQL"
    - "Each portal scrape creates a scrape_runs row with status, listing counts, and duration"
    - "Portals are dispatched to the correct handler based on type (CanadaBuys=CSV, BidsAndTenders=bidsandtenders handler, other=generic browser)"
    - "A failed portal does not stop the pipeline -- errors are caught, logged, and the next portal proceeds"
    - "The CLI supports --portal flag to run a single portal by name"
    - "The pipeline flow is: scrape -> validate -> embed -> upsert -> audit for each portal"
    - "Auto-disable triggers after 5 consecutive portal failures"
    - "Running the scraper twice on the same data upserts without creating duplicates"
  artifacts:
    - path: "scraper/pipeline/audit.py"
      provides: "Scrape run audit logging wrappers"
      exports: ["start_run", "complete_run", "fail_run"]
    - path: "scraper/pipeline/orchestrator.py"
      provides: "Main pipeline loop: portal dispatch, error isolation, flow coordination"
      exports: ["run_pipeline", "scrape_portal"]
    - path: "scraper/main.py"
      provides: "CLI entrypoint with argparse"
      exports: ["main"]
    - path: "scraper/tests/test_audit.py"
      provides: "Audit logging tests"
    - path: "scraper/tests/test_orchestrator.py"
      provides: "Orchestrator dispatch and error isolation tests"
  key_links:
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/pipeline/canadabuys.py"
      via: "Dispatches CanadaBuys portal to canadabuys_ingest"
      pattern: "canadabuys_ingest"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/pipeline/bidsandtenders.py"
      via: "Dispatches BidsAndTenders portals to bidsandtenders_scrape"
      pattern: "bidsandtenders_scrape"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/pipeline/browser_scraper.py"
      via: "Dispatches other portals to browser_scrape"
      pattern: "browser_scrape"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/pipeline/validation.py"
      via: "Validates listings after extraction"
      pattern: "validate_and_score"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/pipeline/embeddings.py"
      via: "Generates embeddings after validation"
      pattern: "generate_embeddings"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/db.py"
      via: "Upserts listings and logs scrape runs"
      pattern: "upsert_listings"
    - from: "scraper/main.py"
      to: "scraper/pipeline/orchestrator.py"
      via: "CLI calls run_pipeline"
      pattern: "run_pipeline"
---

<objective>
Build the orchestrator that ties all pipeline modules together, the audit logging layer, and the CLI entrypoint. Then verify with a live benchmark on 5 representative portals.

Purpose: This is the integration plan that makes the scraper actually run (SCRP-01). The orchestrator dispatches portals to the correct handler, coordinates the validate->embed->upsert flow, and ensures per-portal error isolation. The audit layer (SCRP-03) logs every run. The CLI makes it invokable.

Output: A working `python main.py` that scrapes all enabled portals end-to-end. Verified on 5 representative portals.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/2/2-CONTEXT.md
@.planning/phases/2/2-RESEARCH.md
@.planning/phases/2/2-01-SUMMARY.md
@.planning/phases/2/2-02-SUMMARY.md
@.planning/phases/2/2-03-SUMMARY.md
@scraper/models.py
@scraper/config.py
@scraper/db.py
@scraper/pipeline/validation.py
@scraper/pipeline/canadabuys.py
@scraper/pipeline/embeddings.py
@scraper/pipeline/extraction.py
@scraper/pipeline/bidsandtenders.py
@scraper/pipeline/browser_scraper.py
@scraper/Dockerfile
@scraper/main.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit logging and orchestrator</name>
  <files>
    scraper/pipeline/audit.py
    scraper/pipeline/orchestrator.py
    scraper/tests/test_audit.py
    scraper/tests/test_orchestrator.py
  </files>
  <action>
    **Create `scraper/pipeline/audit.py`:**

    Thin wrappers around db.py scrape run functions with added logging and timing.

    `start_run(conn, portal: PortalRecord) -> str`:
    - Call `db.start_scrape_run(conn, portal.id)`.
    - Log: `f"Starting scrape run for {portal.name} ({portal.url})"`.
    - Return run_id.

    `complete_run(conn, run_id: str, portal: PortalRecord, stats: dict) -> None`:
    - Call `db.complete_scrape_run(conn, run_id, stats)`.
    - Log: `f"Completed {portal.name}: {stats['found']} found, {stats['new']} new, {stats['updated']} updated"`.

    `fail_run(conn, run_id: str, portal: PortalRecord, error: Exception) -> None`:
    - Call `db.fail_scrape_run(conn, run_id, str(error))`.
    - Log error: `f"Failed {portal.name}: {error}"`.
    - Call `db.check_auto_disable(conn, portal.id)` and log if portal was disabled.

    **Create `scraper/pipeline/orchestrator.py`:**

    `def classify_portal(portal: PortalRecord) -> str`:
    - Return `"canadabuys"` if portal.name == "CanadaBuys".
    - Return `"bidsandtenders"` if "bidsandtenders" is in portal.url.
    - Return `"browser"` otherwise.

    `async def scrape_portal(portal: PortalRecord) -> list[ProcurementListing]`:
    - Dispatch based on classify_portal:
      - `"canadabuys"` -> `await canadabuys_ingest(portal)`
      - `"bidsandtenders"` -> `await bidsandtenders_scrape(portal)`
      - `"browser"` -> `await browser_scrape(portal)`
    - Return list of ProcurementListing.

    `async def process_portal(conn, portal: PortalRecord) -> dict`:
    - This is the full pipeline for ONE portal: scrape -> validate -> embed -> upsert -> audit.
    1. `run_id = start_run(conn, portal)`
    2. `try:`
    3.   `raw_listings = await scrape_portal(portal)`
    4.   Convert ProcurementListing to ListingRecord (add source_portal=portal.id, language=portal.language).
    5.   `validated = [validate_and_score(l) for l in listing_records]` — Filter out any that raised ValueError (missing title).
    6.   `embedded = await generate_embeddings(validated)` — Only embed validated listings.
    7.   `stats = upsert_listings(conn, portal.id, embedded)`
    8.   `complete_run(conn, run_id, portal, stats)`
    9.   `return stats`
    10. `except Exception as e:`
    11.   `fail_run(conn, run_id, portal, e)`
    12.   `logger.exception(f"Portal {portal.name} failed")`
    13.   `return {"found": 0, "new": 0, "updated": 0, "error": str(e)}`

    CRITICAL: The except block catches ALL exceptions for error isolation. A failed portal MUST NOT stop the pipeline.

    `async def run_pipeline(portal_name: Optional[str] = None) -> dict`:
    1. `with db_connection() as conn:`
    2.   If portal_name: `portals = [get_portal_by_name(conn, portal_name)]` (raise if not found).
    3.   Else: `portals = get_enabled_portals(conn)`
    4.   Log: `f"Running pipeline for {len(portals)} portals"`
    5.   `results = {}` (portal_name -> stats)
    6.   For each portal (SEQUENTIAL per research: "Sequential portal processing -- memory constraints in 4GB container"):
    7.     `stats = await process_portal(conn, portal)`
    8.     `results[portal.name] = stats`
    9.   Log summary: total portals, total listings found/new/updated, total errors.
    10.  Return results.

    **Create `scraper/tests/test_audit.py`:**
    - `test_start_run_calls_db()` — Verify db.start_scrape_run called with portal.id.
    - `test_complete_run_logs_stats()` — Verify db.complete_scrape_run called and stats logged.
    - `test_fail_run_checks_auto_disable()` — Verify db.check_auto_disable called after failure.

    **Create `scraper/tests/test_orchestrator.py`:**
    - `test_classify_canadabuys()` — CanadaBuys portal returns "canadabuys".
    - `test_classify_bidsandtenders()` — BidsAndTenders URL returns "bidsandtenders".
    - `test_classify_other()` — Other URL returns "browser".
    - `test_process_portal_catches_exceptions()` — Mock scrape_portal to raise, verify stats returned with error (not exception propagated).
    - `test_run_pipeline_processes_all_enabled()` — Mock get_enabled_portals to return 3 portals, verify process_portal called 3 times.
    - `test_run_pipeline_single_portal()` — Verify --portal flag filters to one portal.
    - `test_pipeline_flow_order()` — Mock all pipeline steps, verify call order: scrape -> validate -> embed -> upsert.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/test_audit.py scraper/tests/test_orchestrator.py -x -q 2>&1</automated>
  </verify>
  <done>
    - Orchestrator dispatches portals to correct handler based on URL/name
    - Pipeline flow is scrape -> validate -> embed -> upsert per portal
    - Per-portal error isolation: failed portal logged and skipped, pipeline continues
    - run_pipeline processes portals sequentially
    - Audit wrappers log scrape run start/complete/fail with stats
    - Auto-disable checked after every failure
    - 10+ tests pass with mocked dependencies
  </done>
</task>

<task type="auto">
  <name>Task 2: CLI entrypoint and Dockerfile update</name>
  <files>
    scraper/main.py
    scraper/Dockerfile
  </files>
  <action>
    **Replace `scraper/main.py`** (currently a stub sleep loop):

    ```python
    #!/usr/bin/env python3
    """Procurement scraper pipeline CLI.

    Usage:
      python main.py                    # Run all enabled portals
      python main.py --portal CanadaBuys  # Run single portal by name
      python main.py --list-portals     # List all portals with enabled status
    """
    import argparse
    import asyncio
    import logging
    import sys
    import time

    from scraper.config import LOG_LEVEL
    from scraper.pipeline.orchestrator import run_pipeline
    from scraper.db import db_connection, get_enabled_portals

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("scraper.main")


    def list_portals():
        """Print all portals with their enabled status."""
        from scraper.db import get_connection
        import psycopg2.extras
        conn = get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT name, url, level, province, enabled FROM portals ORDER BY level, province, name")
                rows = cur.fetchall()
            print(f"\n{'Name':<40} {'Level':<12} {'Province':<25} {'Enabled':<8} URL")
            print("-" * 130)
            for r in rows:
                enabled = "YES" if r['enabled'] else "no"
                province = r['province'] or '-'
                print(f"{r['name']:<40} {r['level']:<12} {province:<25} {enabled:<8} {r['url']}")
            print(f"\nTotal: {len(rows)} portals ({sum(1 for r in rows if r['enabled'])} enabled)")
        finally:
            conn.close()


    def main():
        parser = argparse.ArgumentParser(description="Procurement scraper pipeline")
        parser.add_argument("--portal", type=str, help="Run single portal by name")
        parser.add_argument("--list-portals", action="store_true", help="List all portals")
        args = parser.parse_args()

        if args.list_portals:
            list_portals()
            return

        start = time.time()
        logger.info("=" * 60)
        logger.info("PROCUREMENT SCRAPER PIPELINE STARTING")
        logger.info("=" * 60)

        try:
            results = asyncio.run(run_pipeline(portal_name=args.portal))
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
            sys.exit(1)
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            sys.exit(1)

        elapsed = time.time() - start

        # Print summary
        total_found = sum(r.get("found", 0) for r in results.values())
        total_new = sum(r.get("new", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        errors = sum(1 for r in results.values() if "error" in r)

        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Portals processed: {len(results)}")
        logger.info(f"  Listings found: {total_found}")
        logger.info(f"  New listings: {total_new}")
        logger.info(f"  Updated listings: {total_updated}")
        logger.info(f"  Portal errors: {errors}")
        logger.info(f"  Duration: {elapsed:.1f}s")
        logger.info("=" * 60)

        if errors > 0:
            logger.warning(f"{errors} portal(s) had errors -- check logs above")

        # Exit with error code if ALL portals failed
        if errors == len(results) and len(results) > 0:
            sys.exit(1)


    if __name__ == "__main__":
        main()
    ```

    **Update `scraper/Dockerfile`:**
    - Keep the same base image (mcr.microsoft.com/playwright/python:v1.51.0-noble).
    - Update to install browser-use's browser dependencies if needed: `RUN playwright install chromium` (may already be in base image, but ensure it's explicit).
    - Keep the CMD as `["python", "main.py"]` for Docker Compose compatibility (runs all portals).
    - Add a HEALTHCHECK or ensure the container exits cleanly after pipeline completion (don't loop -- let Docker Compose restart policy handle scheduling in Phase 5).

    IMPORTANT change from Phase 1: The scraper should now RUN and EXIT, not sleep forever. The Phase 1 stub was a sleep loop to keep the container alive. Phase 2 scraper should run the pipeline once and exit. Docker Compose restart policy will be adjusted in Phase 5 for scheduling. For now, update docker-compose.yml scraper service to use `restart: "no"` instead of `restart: unless-stopped` so it doesn't restart after completion.

    Actually -- do NOT modify docker-compose.yml in this plan. Just update the Dockerfile. The container behavior change (run once vs loop) is sufficient. Phase 5 handles scheduling.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -c "from scraper.main import main; print('CLI entrypoint imports OK')" && python scraper/main.py --help 2>&1</automated>
    <manual>Verify main.py --help shows --portal and --list-portals flags</manual>
  </verify>
  <done>
    - main.py is a real CLI (not a sleep stub) with argparse
    - `python main.py` runs all enabled portals
    - `python main.py --portal CanadaBuys` runs single portal
    - `python main.py --list-portals` shows all 63 portals with status
    - Pipeline summary printed at end with counts and duration
    - Dockerfile updated for Phase 2 dependencies
    - Exit code 1 only if ALL portals fail
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Live benchmark on 5 representative portals</name>
  <what-built>
    Complete scraper pipeline: CLI entrypoint, three-path ingestion (CanadaBuys CSV, BidsAndTenders browser, generic browser), LLM extraction with instructor + GPT-4o-mini, post-extraction validation, text-embedding-3-small embeddings, PostgreSQL upsert with audit logging.
  </what-built>
  <how-to-verify>
    Run the pipeline against 5 representative portals to validate end-to-end functionality and measure real-world cost:

    1. **Start the database** (if not running):
       ```bash
       cd /Users/clawbot/dev && docker compose up db -d
       ```

    2. **Set up environment** (ensure .env has real OPENAI_API_KEY):
       ```bash
       export $(cat .env | grep -v '^#' | xargs)
       ```

    3. **Install dependencies**:
       ```bash
       cd /Users/clawbot/dev/scraper && pip install -r requirements.txt
       ```

    4. **Run CanadaBuys** (CSV path -- zero LLM cost):
       ```bash
       python main.py --portal "CanadaBuys"
       ```
       Expected: Hundreds of listings from CSV download. Check scrape_runs table for completed status.

    5. **Run one BidsAndTenders portal** (browser path):
       ```bash
       python main.py --portal "Mississauga Bids"
       ```
       Expected: Listings extracted via browser-use + LLM. May take 2-5 minutes.

    6. **Run one generic portal** (browser path):
       ```bash
       python main.py --portal "BC Bid"
       ```
       Expected: Listings extracted via generic browser scraper.

    7. **Verify database state**:
       ```sql
       -- Check listings were inserted
       SELECT source_portal, COUNT(*), AVG(completeness_score) FROM listings
       JOIN portals ON listings.source_portal = portals.id
       GROUP BY source_portal;

       -- Check embeddings exist
       SELECT COUNT(*) FROM listings WHERE embedding IS NOT NULL;

       -- Check scrape_runs audit
       SELECT p.name, sr.status, sr.listings_found, sr.listings_new, sr.duration_seconds
       FROM scrape_runs sr JOIN portals p ON sr.portal_id = p.id
       ORDER BY sr.started_at DESC;

       -- Verify upsert idempotency
       ```

    8. **Re-run CanadaBuys** to verify upsert (no duplicates):
       ```bash
       python main.py --portal "CanadaBuys"
       ```
       Expected: listings_updated > 0, listings_new = 0 (or very few if new postings appeared).

    9. **Check OpenAI usage** in your OpenAI dashboard for cost verification.

    What to report:
    - Number of listings extracted per portal
    - Any extraction errors or empty results
    - Whether embeddings were generated (check listing count with non-null embedding)
    - Approximate cost from OpenAI dashboard
    - Any portals that failed and why
  </how-to-verify>
  <resume-signal>Type "approved" if the benchmark results are acceptable, or describe issues found.</resume-signal>
</task>

</tasks>

<verification>
Run full test suite:
```bash
cd /Users/clawbot/dev
OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/ -x -q
```
All tests pass across all 4 plans.

Then run the 5-portal live benchmark (Task 3 checkpoint).
</verification>

<success_criteria>
1. `python main.py --help` shows usage with --portal and --list-portals flags
2. `python main.py --list-portals` shows all 63 portals (connected to real DB)
3. `python main.py --portal CanadaBuys` downloads CSV, parses, validates, embeds, upserts listings
4. scrape_runs table has a row for CanadaBuys with status='completed', listings_found > 0
5. Re-running CanadaBuys produces listings_updated > 0, not duplicates (SCRP-06 verified)
6. At least one BidsAndTenders portal extracts listings via browser-use
7. All inserted listings have embedding IS NOT NULL (SCRP-05 verified)
8. `pytest scraper/tests/ -x -q` passes all tests
</success_criteria>

<output>
After completion, create `.planning/phases/2/2-04-SUMMARY.md`
</output>
