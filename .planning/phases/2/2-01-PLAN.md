---
phase: 2-scraper-pipeline
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scraper/requirements.txt
  - scraper/config.py
  - scraper/models.py
  - scraper/db.py
  - scraper/pipeline/__init__.py
  - scraper/tests/__init__.py
  - scraper/tests/conftest.py
  - scraper/tests/test_models.py
  - scraper/tests/test_upsert.py
  - pytest.ini
autonomous: true
requirements:
  - SCRP-06

must_haves:
  truths:
    - "Pydantic models validate listing data with correct types and optional fields"
    - "Database upsert inserts new listings and updates existing ones on (source_portal, source_listing_id) conflict"
    - "Connection pool manages PostgreSQL connections with proper cleanup"
    - "All non-required listing fields accept null without validation errors"
    - "Revision counter increments on upsert update"
  artifacts:
    - path: "scraper/requirements.txt"
      provides: "All Phase 2 Python dependencies"
      contains: "instructor"
    - path: "scraper/config.py"
      provides: "Environment configuration and constants"
      contains: "DATABASE_URL"
    - path: "scraper/models.py"
      provides: "Pydantic models for listings, extraction, and scrape runs"
      exports: ["ListingRecord", "ExtractionResult", "ProcurementListing"]
    - path: "scraper/db.py"
      provides: "Database connection pool, upsert_listings, scrape run helpers"
      exports: ["get_connection", "upsert_listings", "get_enabled_portals"]
    - path: "scraper/tests/conftest.py"
      provides: "Shared test fixtures for mocked DB and sample data"
    - path: "scraper/tests/test_models.py"
      provides: "Pydantic model validation tests"
    - path: "scraper/tests/test_upsert.py"
      provides: "Database upsert logic tests"
    - path: "pytest.ini"
      provides: "Pytest configuration"
  key_links:
    - from: "scraper/db.py"
      to: "scraper/models.py"
      via: "upsert_listings accepts ListingRecord objects"
      pattern: "ListingRecord"
    - from: "scraper/db.py"
      to: "scraper/config.py"
      via: "DATABASE_URL from config"
      pattern: "config\\.DATABASE_URL|settings\\.database_url"
---

<objective>
Build the foundation layer for the scraper pipeline: Pydantic data models, database helpers (connection pool, upsert, portal queries), project configuration, and test infrastructure.

Purpose: Every subsequent plan depends on these models and DB helpers. The upsert logic (SCRP-06) is the most critical piece -- it ensures idempotent writes on the (source_portal, source_listing_id) composite key.

Output: Working models.py, db.py, config.py with passing unit tests. All future plans import from these modules.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/2/2-CONTEXT.md
@.planning/phases/2/2-RESEARCH.md
@db/migrations/001_initial_schema.sql
@scraper/main.py
@scraper/requirements.txt
@scraper/Dockerfile
@.env.example
</context>

<tasks>

<task type="auto">
  <name>Task 1: Dependencies, config, and Pydantic models</name>
  <files>
    scraper/requirements.txt
    scraper/config.py
    scraper/models.py
    scraper/pipeline/__init__.py
    pytest.ini
  </files>
  <action>
    **1. Update `scraper/requirements.txt`** — Replace the stub with all Phase 2 dependencies:
    ```
    # Core
    psycopg2-binary==2.9.10
    pydantic>=2.0,<3.0
    httpx>=0.27,<1.0
    openai>=1.0,<2.0
    instructor>=1.0,<2.0

    # Browser automation
    browser-use>=0.11,<1.0
    langchain-openai>=0.1,<1.0

    # Supporting
    beautifulsoup4>=4.0,<5.0
    tenacity>=8.0,<9.0
    tiktoken>=0.5,<1.0

    # Testing
    pytest>=8.0,<9.0
    pytest-asyncio>=0.23,<1.0
    ```

    **2. Create `scraper/config.py`** — Settings from environment variables:
    - `DATABASE_URL` from env (required, no default)
    - `OPENAI_API_KEY` from env (required, no default)
    - `OPENAI_EXTRACTION_MODEL` defaulting to `"gpt-4o-mini"`
    - `OPENAI_EMBEDDING_MODEL` locked to `"text-embedding-3-small"` (per user decision -- model changes require full re-indexing)
    - `EMBEDDING_DIMENSIONS` = 1536
    - `MAX_EMBEDDING_TOKENS` = 8000 (leave margin below 8192 limit)
    - `EMBEDDING_BATCH_TOKEN_LIMIT` = 250_000
    - `EMBEDDING_BATCH_SIZE_LIMIT` = 2048
    - `BROWSER_HEADLESS` = True
    - `BROWSER_WAIT_NETWORK_IDLE` = 2.0 (seconds)
    - `BROWSER_WAIT_BETWEEN_ACTIONS` = 1.0 (seconds)
    - `BROWSER_MAX_STEPS` = 10
    - `PORTAL_CONSECUTIVE_FAILURE_THRESHOLD` = 5 (auto-disable after this many)
    - `LOG_LEVEL` defaulting to `"INFO"`
    - Use `os.environ.get()` with explicit defaults. Raise `ValueError` on missing required vars at import time.
    - Set up logging configuration at module level.

    **3. Create `scraper/models.py`** — Pydantic models matching the DB schema exactly:

    `ProcurementListing` (instructor extraction target):
    - `title: str` (required -- minimum viable listing)
    - `description: Optional[str] = None`
    - `reference_number: Optional[str] = None`
    - `posting_date: Optional[str] = None` (ISO format YYYY-MM-DD)
    - `closing_date: Optional[str] = None` (ISO format)
    - `status: Optional[str] = None` (open/closed/cancelled/awarded)
    - `value_min: Optional[float] = None`
    - `value_max: Optional[float] = None`
    - `contact_name: Optional[str] = None`
    - `contact_email: Optional[str] = None`
    - `contact_phone: Optional[str] = None`
    - `source_url: Optional[str] = None`
    - `source_listing_id: Optional[str] = None`
    - `classification_codes: Optional[list[dict]] = None` (JSONB: [{system, code, description}])
    - `province: Optional[str] = None`
    - `raw_location: Optional[str] = None`
    - `documents: Optional[list[dict]] = None` (JSONB: [{name, type, url, date}])
    - Field descriptions using `Field(description=...)` for instructor's LLM prompt. CRITICAL: Description for classification_codes, value_min, value_max, and closing_date must include "Extract only if explicitly stated in the text. Return null if not clearly present. NEVER guess or infer."

    `ExtractionResult`:
    - `listings: list[ProcurementListing]`

    `ListingRecord` (DB-ready, post-validation):
    - All ProcurementListing fields plus:
    - `source_portal: str` (UUID as string, the portal ID)
    - `embedding: Optional[list[float]] = None`
    - `embedding_model: Optional[str] = None`
    - `language: Optional[str] = None`
    - `completeness_score: float = 0.0`

    `PortalRecord`:
    - `id: str`, `name: str`, `url: str`, `level: str`, `province: Optional[str]`
    - `language: str`, `requires_login: bool`, `enabled: bool`

    `ScrapeRunRecord`:
    - `id: Optional[str]`, `portal_id: str`, `started_at: datetime`
    - `completed_at: Optional[datetime]`, `status: str`
    - `listings_found: int = 0`, `listings_new: int = 0`, `listings_updated: int = 0`
    - `error_message: Optional[str] = None`, `duration_seconds: Optional[float] = None`

    **4. Create `scraper/pipeline/__init__.py`** — Empty file to make pipeline a package.

    **5. Create `pytest.ini`** in the project root:
    ```ini
    [pytest]
    testpaths = scraper/tests
    asyncio_mode = auto
    python_files = test_*.py
    python_functions = test_*
    ```
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && pip install -e scraper/ 2>/dev/null || pip install pydantic>=2.0 && python -c "from scraper.models import ProcurementListing, ListingRecord, ExtractionResult, PortalRecord, ScrapeRunRecord; print('Models OK')" && python -c "from scraper.config import OPENAI_EMBEDDING_MODEL; assert OPENAI_EMBEDDING_MODEL == 'text-embedding-3-small'; print('Config OK')"</automated>
    <manual>Verify models.py field types match db/migrations/001_initial_schema.sql column types</manual>
  </verify>
  <done>
    - requirements.txt lists all Phase 2 dependencies (instructor, browser-use, openai, httpx, beautifulsoup4, tenacity, tiktoken, pytest, pytest-asyncio)
    - config.py loads DATABASE_URL and OPENAI_API_KEY from env, raises on missing
    - models.py defines ProcurementListing, ExtractionResult, ListingRecord, PortalRecord, ScrapeRunRecord with correct types
    - ProcurementListing field descriptions include "never guess" language for classification_codes, values, and dates
    - pipeline/__init__.py exists
    - pytest.ini configures test discovery
  </done>
</task>

<task type="auto">
  <name>Task 2: Database helpers and connection management</name>
  <files>
    scraper/db.py
  </files>
  <action>
    Create `scraper/db.py` with the following functions:

    **Connection management:**
    - `get_connection() -> psycopg2.connection` — Create a connection using `config.DATABASE_URL`. Use `psycopg2.connect()` directly (no pool needed for sequential processing). Register the `psycopg2.extras.Json` adapter for JSONB fields. Set `autocommit=False`.
    - Context manager support: `@contextmanager def db_connection()` that yields a connection and handles commit/rollback/close.

    **Portal queries:**
    - `get_enabled_portals(conn) -> list[PortalRecord]` — `SELECT * FROM portals WHERE enabled = true ORDER BY name`. Return list of PortalRecord.
    - `get_portal_by_name(conn, name: str) -> Optional[PortalRecord]` — Single portal lookup.
    - `disable_portal(conn, portal_id: str) -> None` — `UPDATE portals SET enabled = false, updated_at = NOW() WHERE id = %s`.
    - `check_auto_disable(conn, portal_id: str) -> bool` — Query last 5 scrape_runs for portal. If all 5 have status='failed', call disable_portal and return True. Per user decision: auto-disable after 5 consecutive failures.

    **Listing upsert (SCRP-06):**
    - `upsert_listings(conn, portal_id: str, listings: list[ListingRecord]) -> dict` — Use `psycopg2.extras.execute_values` with the ON CONFLICT upsert SQL from the research. The SQL must:
      - INSERT all listing fields including embedding and embedding_model
      - ON CONFLICT (source_portal, source_listing_id) DO UPDATE all mutable fields
      - SET `last_scraped_at = NOW()`, `updated_at = NOW()`, `revision = listings.revision + 1`
      - Use a CTE or RETURNING clause to count new vs updated rows
    - Return dict: `{"found": N, "new": N, "updated": N}`
    - Handle empty listings list gracefully (return zeros).
    - For the embedding column, use `psycopg2.extras.register_adapter` or pass as string representation for pgvector compatibility. The vector must be passed as a string like `'[0.1, 0.2, ...]'` for the vector type.

    **Scrape run helpers:**
    - `start_scrape_run(conn, portal_id: str) -> str` — INSERT into scrape_runs with started_at=NOW(), status='running'. Return the run ID.
    - `complete_scrape_run(conn, run_id: str, stats: dict) -> None` — UPDATE scrape_runs SET status='completed', completed_at=NOW(), listings_found/new/updated from stats, duration_seconds calculated from started_at.
    - `fail_scrape_run(conn, run_id: str, error_message: str) -> None` — UPDATE scrape_runs SET status='failed', completed_at=NOW(), error_message, duration_seconds.

    **Important implementation details:**
    - Use `%s` parameter style (psycopg2), NOT f-strings for SQL
    - All JSONB fields (classification_codes, contact_info, documents) must be wrapped with `psycopg2.extras.Json()` before insert
    - The embedding vector must be formatted as a string `'[0.1, 0.2, ...]'` for pgvector's vector type
    - Use `psycopg2.extras.RealDictCursor` for queries that return rows
    - Import models from `scraper.models`
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -c "from scraper.db import get_connection, upsert_listings, get_enabled_portals, start_scrape_run, complete_scrape_run, fail_scrape_run, check_auto_disable; print('DB module imports OK')"</automated>
    <manual>Review upsert SQL matches ON CONFLICT (source_portal, source_listing_id) pattern from 001_initial_schema.sql</manual>
  </verify>
  <done>
    - db.py provides connection management with context manager
    - get_enabled_portals returns PortalRecord list from DB
    - upsert_listings handles ON CONFLICT with revision increment and returns new/updated counts
    - start_scrape_run/complete_scrape_run/fail_scrape_run manage the scrape_runs audit table
    - check_auto_disable queries last 5 runs and disables portal after 5 consecutive failures
    - All SQL uses parameterized queries, no string interpolation
  </done>
</task>

<task type="auto">
  <name>Task 3: Test infrastructure and unit tests</name>
  <files>
    scraper/tests/__init__.py
    scraper/tests/conftest.py
    scraper/tests/test_models.py
    scraper/tests/test_upsert.py
  </files>
  <action>
    **1. Create `scraper/tests/__init__.py`** — Empty file.

    **2. Create `scraper/tests/conftest.py`** — Shared fixtures:
    - `sample_listing_dict()` — Returns a dict with all listing fields populated (title, description, dates, codes, values, contact, documents, source_url, source_listing_id). Use realistic Canadian procurement data.
    - `sample_listing_minimal()` — Returns a dict with only minimum viable fields: title, source_url, source_portal (everything else null).
    - `sample_portal_dict()` — Returns a dict matching PortalRecord fields.
    - `mock_db_connection()` — A mock psycopg2 connection with mock cursor that supports execute, execute_values, fetchall, fetchone. Use `unittest.mock.MagicMock`.
    - `sample_html_content()` — A realistic HTML snippet of a procurement listing page (3-4 listings in a table) for extraction tests in later plans.
    - `mock_openai_client()` — Mock that returns predefined embedding vectors (list of 1536 floats, all 0.1) and predefined extraction responses. For use in later plans.

    **3. Create `scraper/tests/test_models.py`** — Tests for Pydantic models:
    - `test_procurement_listing_all_fields()` — Construct with all fields, verify serialization.
    - `test_procurement_listing_minimal()` — Construct with only title, verify all Optional fields are None.
    - `test_procurement_listing_rejects_missing_title()` — Verify ValidationError when title is missing.
    - `test_listing_record_includes_portal_and_embedding()` — Verify ListingRecord accepts embedding list and portal ID.
    - `test_extraction_result_contains_listings()` — Verify ExtractionResult wraps list of ProcurementListing.
    - `test_portal_record_from_dict()` — Construct PortalRecord from dict.
    - `test_listing_record_null_optional_fields()` — All optional fields accept None without error.
    - `test_classification_codes_jsonb_format()` — Verify classification_codes accepts list of {system, code, description} dicts.

    **4. Create `scraper/tests/test_upsert.py`** — Tests for DB upsert logic:
    - `test_upsert_sql_contains_on_conflict()` — Verify the UPSERT_SQL string contains "ON CONFLICT (source_portal, source_listing_id)".
    - `test_upsert_empty_list_returns_zeros()` — Call upsert_listings with empty list, verify returns {"found": 0, "new": 0, "updated": 0}.
    - `test_upsert_calls_execute_values()` — Mock the cursor, call upsert_listings with 2 listings, verify execute_values was called with correct number of value tuples.
    - `test_start_scrape_run_inserts_running()` — Mock cursor, verify INSERT contains status='running'.
    - `test_complete_scrape_run_updates_stats()` — Mock cursor, verify UPDATE sets correct fields.
    - `test_fail_scrape_run_sets_error()` — Mock cursor, verify error_message is set.
    - `test_check_auto_disable_triggers_after_5_failures()` — Mock cursor to return 5 rows all with status='failed', verify disable_portal is called.
    - `test_check_auto_disable_does_not_trigger_with_success()` — Mock cursor to return 4 failed + 1 completed, verify disable_portal is NOT called.

    All tests use mocked database connections (no real DB required). Tests should be fast (<2 seconds total).
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && pip install pydantic pytest pytest-asyncio psycopg2-binary 2>/dev/null && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/test_models.py scraper/tests/test_upsert.py -x -q 2>&1</automated>
  </verify>
  <done>
    - conftest.py provides sample_listing_dict, sample_listing_minimal, mock_db_connection fixtures
    - test_models.py has 8+ tests covering Pydantic model validation (all pass)
    - test_upsert.py has 8+ tests covering upsert logic with mocked DB (all pass)
    - All tests run in under 2 seconds with no external dependencies
    - `pytest scraper/tests/ -x -q` exits 0
  </done>
</task>

</tasks>

<verification>
Run full test suite after all tasks:
```bash
cd /Users/clawbot/dev
OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/ -x -q
```
All tests pass. Models import cleanly. DB module imports cleanly.
</verification>

<success_criteria>
1. `from scraper.models import ProcurementListing, ListingRecord, ExtractionResult` succeeds
2. `from scraper.db import upsert_listings, get_enabled_portals` succeeds
3. `from scraper.config import DATABASE_URL, OPENAI_API_KEY` raises ValueError (no env vars) -- correct behavior
4. `pytest scraper/tests/ -x -q` passes all tests (8+ model tests, 8+ upsert tests)
5. The upsert SQL uses ON CONFLICT (source_portal, source_listing_id) DO UPDATE
6. ProcurementListing field descriptions include "never guess" instructions for structured fields
</success_criteria>

<output>
After completion, create `.planning/phases/2/2-01-SUMMARY.md`
</output>
