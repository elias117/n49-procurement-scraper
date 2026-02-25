---
phase: 6-keyword-infrastructure
plan: 02
type: execute
wave: 2
depends_on:
  - 6-01
files_modified:
  - scraper/pipeline/orchestrator.py
  - scraper/Dockerfile
  - scraper/tests/test_orchestrator.py
autonomous: true
requirements:
  - FILT-01
  - FILT-05

must_haves:
  truths:
    - "CanadaBuys listings are filtered by keyword match before upsert"
    - "Only keyword-matching listings reach the database"
    - "Deduplication runs on every portal's listings before validation"
    - "Keywords are loaded once at pipeline startup, not per-portal"
    - "Keywords CSV is available inside the Docker container"
    - "Pipeline logs total parsed vs matched count for observability"
  artifacts:
    - path: "scraper/pipeline/orchestrator.py"
      provides: "Keyword-filtered pipeline with dedup"
      contains: "load_keywords"
    - path: "scraper/Dockerfile"
      provides: "Keywords CSV copied into Docker image"
      contains: "keywords_library.csv"
  key_links:
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/pipeline/keywords.py"
      via: "import and call load_keywords, filter_listings, deduplicate_listings"
      pattern: "from scraper\\.pipeline\\.keywords import"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/db.py"
      via: "upsert_listings receives only filtered+deduped listings"
      pattern: "upsert_listings"
    - from: "scraper/Dockerfile"
      to: "keywords_library.csv"
      via: "COPY into Docker image"
      pattern: "COPY keywords_library.csv"
---

<objective>
Wire keyword filtering and deduplication into the pipeline orchestrator and ensure the keywords CSV is available in Docker.

Purpose: This integrates the keyword module (from plan 6-01) into the live scraper pipeline so CanadaBuys listings are filtered before upsert, and all portals get deduplication. Also ensures the Docker container has access to the keywords CSV.

Output: Modified `scraper/pipeline/orchestrator.py` with keyword loading, filtering, and dedup integrated. Modified `scraper/Dockerfile` with COPY for keywords CSV.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/6/6-CONTEXT.md
@.planning/phases/6/6-RESEARCH.md
@.planning/phases/6/6-01-SUMMARY.md
@scraper/pipeline/orchestrator.py
@scraper/pipeline/keywords.py
@scraper/Dockerfile
@scraper/tests/test_orchestrator.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Integrate keyword loading, filtering, and dedup into orchestrator</name>
  <files>scraper/pipeline/orchestrator.py, scraper/tests/test_orchestrator.py</files>
  <action>
Modify `scraper/pipeline/orchestrator.py`:

**1. Add import at top of file:**
```python
from scraper.pipeline.keywords import load_keywords, filter_listings, deduplicate_listings
```

**2. Modify `run_pipeline()` function signature and body:**

Add keyword loading BEFORE the `with db_connection() as conn:` block. This ensures the fail-safe SystemExit happens before any database operations.

```python
async def run_pipeline(
    portal_name: Optional[str] = None,
    skip_embeddings: bool = False,
) -> dict:
    # Load keywords at startup (fail-safe: SystemExit if missing/malformed)
    keywords = load_keywords()

    with db_connection() as conn:
        # ... existing portal fetching logic (unchanged) ...

        results = {}
        for portal in portals:
            logger.info(
                "--- Processing portal: %s (%s) ---", portal.name, portal.url
            )
            stats = await process_portal(
                conn, portal, keywords=keywords, skip_embeddings=skip_embeddings
            )
            results[portal.name] = stats

        # ... existing summary logging (unchanged) ...
        return results
```

Note: Do NOT add the purge call here yet -- that is Plan 6-03.

**3. Modify `process_portal()` function signature:**

Add `keywords: list[str] | None = None` parameter. The `None` default preserves backward compatibility for tests that call `process_portal` directly without keywords.

**4. Add filtering and dedup steps in `process_portal()`:**

Insert TWO new steps between the existing Step 2 (ListingRecord conversion, ends at line ~106) and Step 3 (validation, starts at line ~109):

```python
        # Step 2.5: Keyword filtering (if keywords provided)
        if keywords:
            listing_records = filter_listings(listing_records, keywords)

        # Step 2.6: Deduplication (always runs -- safety net for all portals)
        listing_records = deduplicate_listings(listing_records)
```

Place these AFTER the `listing_records` list is fully built (after the for-loop over `raw_listings`) and BEFORE the validation loop.

**Important:** Do NOT change the existing step numbering in comments -- just add the new steps with 2.5 and 2.6 numbering between existing steps. Keep all existing code (scrape, convert, validate, embed, upsert, audit) unchanged.

**5. Update test_orchestrator.py if needed:**

Read the existing `test_orchestrator.py` to understand current test patterns. If tests call `process_portal()` directly, they should still work because `keywords` defaults to `None` (no filtering applied). If any test assertions break due to the new parameter, fix them. Do NOT delete or reduce existing test coverage.

If the existing tests mock `process_portal`, update the mock call signatures to accept the new `keywords` parameter.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -m pytest scraper/tests/test_orchestrator.py scraper/tests/test_keywords.py -x -q</automated>
    <manual>Verify orchestrator imports keywords module and passes keywords through pipeline</manual>
  </verify>
  <done>
    - `run_pipeline()` calls `load_keywords()` once before the portal loop
    - `process_portal()` accepts optional `keywords` parameter
    - When keywords provided, `filter_listings()` runs between ListingRecord conversion and validation
    - `deduplicate_listings()` always runs (even without keywords)
    - All existing orchestrator tests still pass
    - Keywords are passed from `run_pipeline()` to `process_portal()`
  </done>
</task>

<task type="auto">
  <name>Task 2: Add keywords CSV COPY to Dockerfile</name>
  <files>scraper/Dockerfile</files>
  <action>
Add a COPY line to `scraper/Dockerfile` to include `keywords_library.csv` in the Docker image.

The Dockerfile's build context is `.` (repo root, confirmed in `docker-compose.yml` line `context: .`), so the CSV is accessible.

Add this line AFTER the existing `COPY scraper/ ./scraper/` line (line 18) and BEFORE the CMD line:

```dockerfile
COPY keywords_library.csv ./keywords_library.csv
```

This places it at `/app/keywords_library.csv` in the container.

The `KEYWORDS_CSV_PATH` in `keywords.py` resolves using `Path(__file__).resolve().parent.parent.parent / "keywords_library.csv"`:
- `__file__` = `/app/scraper/pipeline/keywords.py`
- `.parent` = `/app/scraper/pipeline/`
- `.parent` = `/app/scraper/`
- `.parent` = `/app/`
- Result: `/app/keywords_library.csv`

This matches the COPY destination. No path changes needed.

Do NOT change any other Dockerfile lines. Preserve the existing structure exactly.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && grep -n "keywords_library.csv" scraper/Dockerfile && echo "COPY line present"</automated>
    <manual>Verify the COPY line is in the correct position in the Dockerfile</manual>
  </verify>
  <done>
    - `scraper/Dockerfile` contains `COPY keywords_library.csv ./keywords_library.csv`
    - COPY is placed after `COPY scraper/ ./scraper/` and before `CMD`
    - Path resolves to `/app/keywords_library.csv` matching the `KEYWORDS_CSV_PATH` constant
  </done>
</task>

</tasks>

<verification>
1. `cd /Users/clawbot/dev && python -m pytest scraper/tests/ -x -q` -- full scraper test suite passes
2. `cd /Users/clawbot/dev && grep "from scraper.pipeline.keywords import" scraper/pipeline/orchestrator.py` -- import present
3. `cd /Users/clawbot/dev && grep "filter_listings\|deduplicate_listings\|load_keywords" scraper/pipeline/orchestrator.py` -- all three functions referenced
4. `cd /Users/clawbot/dev && grep "keywords_library.csv" scraper/Dockerfile` -- COPY line present
</verification>

<success_criteria>
- `orchestrator.py` loads keywords once at pipeline startup via `load_keywords()`
- `process_portal()` filters listings by keyword and deduplicates before validation
- `Dockerfile` copies `keywords_library.csv` into the Docker image at `/app/keywords_library.csv`
- All existing tests pass without modification (or with minimal signature updates)
- Keywords parameter is optional on `process_portal()` for backward compatibility
</success_criteria>

<output>
After completion, create `.planning/phases/6/6-02-SUMMARY.md`
</output>
