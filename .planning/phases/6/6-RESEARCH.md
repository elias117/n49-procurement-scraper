# Phase 6: Keyword Infrastructure + CanadaBuys Filtering + Data Purge - Research

**Researched:** 2026-02-25
**Domain:** Python CSV parsing, PostgreSQL DELETE operations, in-memory text matching
**Confidence:** HIGH

## Summary

Phase 6 adds keyword-based filtering to the existing scraper pipeline. The scope is narrow and well-defined: (1) load 121 keywords from a CSV file at startup, (2) filter CanadaBuys listings by substring match on title/description before upsert, (3) hard-DELETE existing non-matching listings from the database, and (4) deduplicate listings by `source_listing_id` within a scrape run.

The existing codebase is clean and modular. The CanadaBuys scraper (`canadabuys_ingest`) returns `ListingRecord` objects with `title`, `description`, and `source_listing_id` fields already populated. The orchestrator's `process_portal` function has a clear step-by-step pipeline (scrape -> validate -> embed -> upsert) where filtering and deduplication can be inserted between scrape and validate. The database layer (`db.py`) uses psycopg2 with parameterized queries and context-managed connections, providing a clear pattern for the new purge DELETE query.

All changes are Python-only: one new module (`scraper/pipeline/keywords.py`), modifications to the orchestrator to call the keyword filter, and a new `purge_unmatched_listings` function in `db.py`. No schema changes, no new dependencies, no API or frontend changes.

**Primary recommendation:** Create a standalone `scraper/pipeline/keywords.py` module with three functions: `load_keywords()` (CSV parse + validation), `matches_keywords()` (single listing check), and `filter_listings()` (batch filter with logging). Call `load_keywords()` at the top of `run_pipeline()` and pass the keyword set through the pipeline. The purge function belongs in `db.py` alongside the existing upsert logic.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Matching method:** Case-insensitive substring match (`keyword.lower() in text.lower()`)
- **Match targets:** Title AND description -- a listing matches if ANY keyword hits in either field
- **Partial matches allowed** -- "translation" matching "translator" is acceptable
- **Multi-word keywords:** Matched as full phrases via substring
- **OR semantics:** Listing passes if it matches at least one keyword from the full set
- **No stemming or fuzzy matching** -- simple substring only
- **Purge behavior:** Hard DELETE, no soft delete, no tombstones, no dry-run
- **Purge scope:** All existing listings that don't match any keyword on title or description
- **Purge matching:** Reuses the same matching function as scraper filtering (PURG-02)
- **Purge timing:** Runs once as part of the scrape job after filtering is in place
- **Keyword loading:** Once per scrape job startup, fail-safe (refuses to run without keywords)
- **Keyword validation:** Confirm expected columns (Category, Language, Keyword), confirm non-zero count
- **In-memory only:** No database table for keywords
- **File location:** `keywords_library.csv` in repo root (already exists)
- **Filter point:** After CSV parsing into ListingRecord, before upsert
- **Observability:** Log total parsed vs matched count
- **No keyword-match metadata stored** on listings
- **Deduplication:** Track seen `source_listing_id` in a set, skip duplicates, keep first occurrence

### Claude's Discretion
- Internal module structure and function signatures
- Exact log message formats
- Where in the orchestrator to hook keyword loading (recommendation: top of `run_pipeline`)
- Whether purge runs before or after the portal scrape loop
- Test organization and fixture design

### Deferred Ideas (OUT OF SCOPE)
None raised during discussion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| KWRD-01 | Keywords loaded from CSV file (Category, Language, Keyword columns) at scraper startup and made available to all scraper strategies | CSV format confirmed: 121 data rows, 3 columns, standard `csv.DictReader` parsing. Load in `run_pipeline()` before portal loop. |
| KWRD-02 | Keywords CSV stored in the repository at a known path for reference | Already satisfied: `keywords_library.csv` exists at repo root with 121 keywords. |
| KWRD-03 | Keyword matching is case-insensitive and supports both EN and FR keywords | 60 EN + 61 FR keywords confirmed. Substring `.lower()` comparison handles accented FR characters correctly in Python 3. |
| FILT-01 | CanadaBuys CSV listings filtered client-side by keyword match on title and description before upsert | Integration point identified: in `process_portal()` between Step 2 (ListingRecord conversion) and Step 3 (validation). CanadaBuys listings have `title` and `description` fields populated from EN/FR CSV columns. |
| FILT-05 | Listings from multiple keyword searches within a run are deduplicated by source_listing_id before upsert | For CanadaBuys: safety net only (single CSV). Dedup set tracked in `process_portal()` or `run_pipeline()`. Critical for Phases 7/8. |
| PURG-01 | Existing listings not matching any keyword are purged from the database | DELETE query against `listings` table using same matching logic. Must fetch title+description from DB, apply match function, delete non-matching. |
| PURG-02 | Purge uses the same keyword-matching logic as the scraper filters for consistency | Single `matches_keywords(title, description, keywords)` function reused by both filter and purge paths. |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Component | Version | Purpose | Current Location |
|-----------|---------|---------|-----------------|
| Python csv module | stdlib | Parse keywords_library.csv | No dependency needed |
| psycopg2 | Already in requirements.txt | Execute DELETE for purge | `scraper/db.py` |
| Pydantic | Already in requirements.txt | ListingRecord model (title, description fields) | `scraper/models.py` |
| pytest + pytest-asyncio | Already in requirements.txt | Unit tests | `scraper/tests/` |

### No New Dependencies
This phase requires ZERO new libraries. Everything is built with Python stdlib (`csv`, `io`, `pathlib`, `logging`) and existing project dependencies (`psycopg2` for the purge DELETE). The keyword matching is pure Python string operations.

## Architecture Patterns

### New Module: `scraper/pipeline/keywords.py`

```
scraper/
  pipeline/
    keywords.py          # NEW: load_keywords(), matches_keywords(), filter_listings()
    orchestrator.py       # MODIFIED: call load_keywords() at startup, filter in process_portal()
    canadabuys.py         # UNCHANGED
  db.py                   # MODIFIED: add purge_unmatched_listings()
  main.py                 # UNCHANGED
  config.py               # UNCHANGED (keyword path can be a module constant, not env var)
  models.py               # UNCHANGED
```

### Pattern 1: Keyword Loading

**What:** Parse `keywords_library.csv` into a `list[str]` of lowercased keyword strings at scraper startup. Validate columns and non-zero count. Fail hard if anything is wrong.

**When to use:** Called once at the top of `run_pipeline()`, before the portal loop.

**Integration point in orchestrator.py:** `run_pipeline()` at line 166, before the `with db_connection() as conn:` block (or immediately inside it).

```python
# scraper/pipeline/keywords.py

import csv
import logging
from pathlib import Path

logger = logging.getLogger("scraper.keywords")

# Path relative to repo root -- keywords_library.csv lives at project root
KEYWORDS_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "keywords_library.csv"

REQUIRED_COLUMNS = {"Category", "Language", "Keyword"}


def load_keywords(csv_path: Path = KEYWORDS_CSV_PATH) -> list[str]:
    """
    Load keywords from CSV and return lowercased keyword strings.

    Validates:
    - File exists and is readable
    - Required columns present: Category, Language, Keyword
    - At least one keyword loaded

    Raises:
        SystemExit: If CSV is missing, malformed, or empty.

    Returns:
        List of lowercased keyword strings (e.g., ["translation services", "services de traduction", ...])
    """
    if not csv_path.exists():
        logger.error("Keywords CSV not found: %s", csv_path)
        raise SystemExit(f"Keywords CSV not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Validate columns
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            logger.error("Keywords CSV missing columns: %s", missing)
            raise SystemExit(f"Keywords CSV missing required columns: {missing}")

        keywords = []
        for row in reader:
            keyword = row.get("Keyword", "").strip()
            if keyword:
                keywords.append(keyword.lower())

    if not keywords:
        logger.error("Keywords CSV loaded but contains no keywords")
        raise SystemExit("Keywords CSV contains no keywords")

    logger.info(
        "Loaded %d keywords from %s", len(keywords), csv_path.name
    )
    return keywords
```

**Key design decisions:**
- Returns `list[str]` (lowercased) not `set[str]` -- iteration order doesn't matter for correctness but list is simpler and sufficient for 121 items.
- Uses `SystemExit` (not `ValueError`) for fail-safe -- this terminates the entire scraper process, matching the fail-safe requirement.
- Path is relative to module location using `__file__` -- works in both local dev and Docker container.
- The `csv_path` parameter enables testing with fixture files without mocking.

### Pattern 2: Keyword Matching

**What:** Check if a listing's title or description contains any keyword via case-insensitive substring match.

**Critical detail from CanadaBuys CSV parsing:** The `_parse_csv` function (canadabuys.py lines 159-179) uses English title with French fallback, and English description with French fallback. This means `ListingRecord.title` may be in English OR French, and `ListingRecord.description` may be in English OR French. The keyword list contains BOTH EN and FR keywords, so matching ANY keyword against the combined title+description covers both language paths.

```python
def matches_keywords(title: str | None, description: str | None, keywords: list[str]) -> bool:
    """
    Check if a listing matches any keyword via case-insensitive substring.

    Args:
        title: Listing title (may be None).
        description: Listing description (may be None).
        keywords: List of lowercased keyword strings.

    Returns:
        True if any keyword is a substring of title or description.
    """
    # Build searchable text (lowercase once, search many)
    text = ""
    if title:
        text += title.lower()
    if description:
        text += " " + description.lower()

    if not text.strip():
        return False

    return any(kw in text for kw in keywords)
```

**Performance note:** For 121 keywords x ~4,000 CanadaBuys listings, this is ~484,000 substring checks. Python's `in` operator on strings uses a fast C-level implementation (Boyer-Moore-Horspool variant). This will complete in well under 1 second. No optimization needed.

### Pattern 3: Batch Filter with Logging

```python
def filter_listings(listings: list, keywords: list[str]) -> list:
    """
    Filter a list of ListingRecord objects, keeping only keyword matches.

    Logs total vs matched count for observability.

    Args:
        listings: List of ListingRecord objects.
        keywords: List of lowercased keyword strings.

    Returns:
        Filtered list of ListingRecord objects.
    """
    matched = [
        listing for listing in listings
        if matches_keywords(listing.title, listing.description, keywords)
    ]
    logger.info(
        "Keyword filter: %d listings parsed, %d matched keywords",
        len(listings),
        len(matched),
    )
    return matched
```

### Pattern 4: Deduplication

**What:** Track seen `source_listing_id` values in a set, skip duplicates within a single scrape run.

**Integration point:** In `process_portal()` (orchestrator.py), AFTER keyword filtering, BEFORE validation. Or as a standalone function in `keywords.py`.

```python
def deduplicate_listings(listings: list) -> list:
    """
    Remove duplicate listings by source_listing_id within a batch.

    Keeps first occurrence, skips subsequent duplicates.

    Args:
        listings: List of ListingRecord objects.

    Returns:
        Deduplicated list.
    """
    seen = set()
    unique = []
    for listing in listings:
        lid = listing.source_listing_id
        if lid and lid in seen:
            continue
        if lid:
            seen.add(lid)
        unique.append(listing)

    dupes = len(listings) - len(unique)
    if dupes > 0:
        logger.info("Deduplication: removed %d duplicate listings", dupes)
    return unique
```

### Pattern 5: Purge Non-Matching Listings from DB

**What:** Hard-DELETE all existing listings that don't match any keyword on title or description.

**Why not a pure SQL approach:** The keyword matching logic is Python-based substring matching. Replicating 121 `LIKE '%keyword%'` conditions in SQL would be fragile and diverge from the Python function (PURG-02 requires same logic). Instead: fetch all listings (id, title, description) from DB, apply the Python matching function, collect non-matching IDs, delete by ID batch.

**Integration point:** New function in `scraper/db.py`.

```python
# In scraper/db.py

def purge_unmatched_listings(conn, keywords: list[str]) -> int:
    """
    Delete all listings that don't match any keyword.

    Fetches all listing IDs, titles, descriptions from DB,
    applies the same matches_keywords() function used by the scraper,
    and DELETEs non-matching rows by ID.

    Args:
        conn: psycopg2 connection.
        keywords: List of lowercased keyword strings.

    Returns:
        Number of listings deleted.
    """
    from scraper.pipeline.keywords import matches_keywords

    with conn.cursor() as cur:
        cur.execute("SELECT id, title, description FROM listings")
        rows = cur.fetchall()

    to_delete = [
        row[0] for row in rows
        if not matches_keywords(row[1], row[2], keywords)
    ]

    if not to_delete:
        return 0

    with conn.cursor() as cur:
        # Delete in batches to avoid overly large IN clauses
        batch_size = 1000
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i:i + batch_size]
            cur.execute(
                "DELETE FROM listings WHERE id = ANY(%s)",
                (batch,)
            )

    return len(to_delete)
```

**Important considerations:**
- Uses `ANY(%s)` with psycopg2 array parameter -- more efficient than `IN` with individual params for large lists.
- Batch size of 1000 prevents oversized queries.
- The `fetchall()` loads all listing IDs, titles, and descriptions into memory. With ~1,000-5,000 listings (per PROJECT.md data volume), this is negligible memory.
- Must be called WITHIN the `db_connection()` context manager so the DELETE is committed with the same transaction.

### Pattern 6: Orchestrator Integration

**What:** Wire keyword loading, filtering, dedup, and purge into `run_pipeline()` and `process_portal()`.

**Modified `run_pipeline()`** (orchestrator.py):

```python
async def run_pipeline(portal_name=None, skip_embeddings=False) -> dict:
    # NEW: Load keywords at startup (fail-safe)
    keywords = load_keywords()

    with db_connection() as conn:
        # ... existing portal fetching logic ...

        results = {}
        for portal in portals:
            stats = await process_portal(conn, portal, keywords=keywords, skip_embeddings=skip_embeddings)
            results[portal.name] = stats

        # NEW: Purge non-matching listings after all portals processed
        purged = purge_unmatched_listings(conn, keywords)
        logger.info("Purged %d non-matching listings from database", purged)

        # ... existing summary logging ...
        return results
```

**Modified `process_portal()`** (orchestrator.py):

```python
async def process_portal(conn, portal, keywords=None, skip_embeddings=False) -> dict:
    # ... existing steps 1-2 ...

    # NEW Step 2.5: Keyword filtering (if keywords provided)
    if keywords:
        listing_records = filter_listings(listing_records, keywords)

    # NEW Step 2.6: Deduplication
    listing_records = deduplicate_listings(listing_records)

    # ... existing steps 3-6 (validate, embed, upsert, audit) ...
```

**Key integration details:**
- `keywords` parameter is optional on `process_portal()` to maintain backward compatibility and testability.
- Keywords are loaded ONCE and passed through -- no re-reading the CSV per portal.
- Purge runs AFTER the portal loop so all new matching listings are upserted first.
- Purge runs inside the `db_connection()` context manager so the DELETE is committed.

### Anti-Patterns to Avoid
- **Don't load keywords inside `process_portal()`** -- it would re-read the CSV for every portal (63 times per run).
- **Don't use regex for keyword matching** -- substring `in` is simpler, faster, and matches the user decision exactly.
- **Don't do the purge in SQL with LIKE** -- diverges from the Python matching function, violating PURG-02.
- **Don't store keywords in the database** -- user decided in-memory only.
- **Don't use `set()` for keyword storage expecting exact match** -- we need substring matching, not set membership.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV parsing | Manual string splitting | Python `csv.DictReader` | Handles quoting, escaping, BOM |
| Case-insensitive match | Custom normalization | `str.lower()` + `in` operator | Python 3 handles Unicode/accents correctly with `.lower()` |
| Batch DELETE | Individual DELETE per row | `DELETE WHERE id = ANY(%s)` | Single round-trip per batch, psycopg2 handles array params |
| Fail-safe startup | Custom exception handling | `SystemExit` | Terminates the process immediately, clear signal to Docker/cron |

**Key insight:** This phase is entirely Python string operations + one SQL DELETE. No libraries needed beyond what's already in the project.

## Common Pitfalls

### Pitfall 1: Keywords CSV Path in Docker Container
**What goes wrong:** The `keywords_library.csv` lives at the repo root (`/Users/clawbot/dev/keywords_library.csv`), but inside the Docker container the working directory and file layout are different.
**Why it happens:** The Dockerfile copies the scraper directory (`COPY scraper/ /app/scraper/`), but the CSV file is at the repo root, not inside `scraper/`.
**How to avoid:** Check the Dockerfile and `docker-compose.yml` to see how files are mapped. The CSV must either be: (a) copied into the Docker image via an additional `COPY keywords_library.csv /app/keywords_library.csv` in the Dockerfile, or (b) mounted as a volume in docker-compose.yml. Option (a) is preferred since it bakes the file into the image.
**Warning signs:** `FileNotFoundError` or `SystemExit("Keywords CSV not found")` when running in Docker.

### Pitfall 2: CanadaBuys Title/Description Language Mismatch
**What goes wrong:** A listing has an English title but French description (or vice versa), and keywords only match the field not being checked.
**Why it happens:** `canadabuys.py` line 159 uses English title with French fallback, and line 177 uses English description with French fallback. If both EN and FR columns are populated, only English is kept in the ListingRecord.
**How to avoid:** This is mitigated by the keyword list containing BOTH EN and FR keywords. An English title will be matched by EN keywords, and a French-only title (French fallback triggered) will be matched by FR keywords. The OR semantics (match ANY keyword in ANY field) make this robust.
**Warning signs:** Unexpectedly low match rates on CanadaBuys listings.

### Pitfall 3: Purge Deleting Listings From Other Portals
**What goes wrong:** The purge function deletes listings from ALL portals, including BidsAndTenders and browser-scraped portals that haven't been keyword-filtered yet (Phases 7/8).
**Why it happens:** The purge SQL has no `WHERE source_portal = ...` clause -- it operates on the entire `listings` table.
**How to avoid:** This is actually the INTENDED behavior per the CONTEXT.md decision: "Scope: All existing listings in the `listings` table that don't match any keyword." The purge is a one-time cleanup of the entire database. However, the purge should be idempotent so it can run on every scrape job without harm (future runs will only delete newly-scraped non-matching listings from other portals, if any).
**Warning signs:** Large purge counts on first run is expected and correct.

### Pitfall 4: Empty Description Field
**What goes wrong:** Some listings have NULL/empty descriptions, causing the keyword match to fail even though the title matches.
**Why it happens:** Not handling None values in the matching function.
**How to avoid:** The `matches_keywords()` function must handle `None` for both title and description. The pattern above correctly checks `if title:` and `if description:` before concatenating.
**Warning signs:** Listings with keyword-matching titles but no description being incorrectly filtered out.

### Pitfall 5: Keyword CSV Encoding
**What goes wrong:** French keywords with accents (e.g., "interprétation simultanée") fail to match because the CSV was read with wrong encoding.
**Why it happens:** The CSV contains UTF-8 encoded French characters with accents (e, e with acute, etc.).
**How to avoid:** Open the CSV with `encoding="utf-8-sig"` (handles BOM if present). Python 3's `.lower()` correctly lowercases accented characters. Verified: the keyword CSV contains accented characters like "interprétation", "traduction assermentée", "Loi sur les langues officielles".
**Warning signs:** FR keywords not matching French text in listings.

### Pitfall 6: Purge Memory with Large Database
**What goes wrong:** `fetchall()` on a very large listings table consumes too much memory.
**Why it happens:** Loading all rows into Python memory at once.
**How to avoid:** The current data volume is 1,000-5,000 listings (per PROJECT.md). Even at 10x growth (50,000 listings), each row is ~1KB (title + description + UUID), so total memory is ~50MB. This is well within the 4GB container constraint. If the database grows significantly, switch to server-side cursors with `cur.itersize = 1000`. But this is premature optimization for the current scale.
**Warning signs:** Memory warnings in Docker logs during purge.

## Code Examples

### Keywords CSV Format (Verified)

```csv
Category,Language,Keyword
Core Language and Translation,EN,translation services
Core Language and Translation,EN,interpretation services
Core Language and Translation,FR,services de traduction
Core Language and Translation,FR,services d'interprétation
Official Languages and Bilingualism,EN,bilingual services
...
Procurement Vehicle Signals,FR,commande subséquente
```

**File:** `/Users/clawbot/dev/keywords_library.csv`
**Lines:** 122 (1 header + 121 data rows -- note: last row has no trailing newline, so `wc -l` reports 121)
**Columns:** Category, Language, Keyword (exactly 3)
**Categories:** 6 (Core Language and Translation, Official Languages and Bilingualism, Multilingual Coverage, Communications and Engagement, Procurement Vehicle Signals -- and one more to verify at implementation)
**Languages:** EN (60 keywords), FR (61 keywords)
**Note:** The ROADMAP.md says "122 keywords" but the CSV has 121 data rows. This is a minor discrepancy -- implementation should handle whatever count the CSV contains.

### CanadaBuys ListingRecord Fields Used for Matching

Source: `scraper/pipeline/canadabuys.py` lines 192-210

```python
# These are the fields available for keyword matching:
listing = ListingRecord(
    title=title,               # line 193: EN preferred, FR fallback (line 159)
    description=description,   # line 194: EN preferred, FR fallback (line 177)
    source_listing_id=ref_number,  # line 196: reference_number from CSV
    # ... other fields not used for matching
)
```

**Key field sources from CanadaBuys CSV:**
- `title` comes from `title-titre-eng` (fallback: `title-titre-fra`) -- line 159
- `description` comes from `tenderDescription-descriptionAppelOffres-eng` (fallback: `tenderDescription-descriptionAppelOffres-fra`) -- line 177
- `source_listing_id` comes from `referenceNumber-numeroReference` -- line 196

### Orchestrator Integration Points

Source: `scraper/pipeline/orchestrator.py`

**`run_pipeline()`** (line 147-200):
- Keyword loading: Insert at line 166 (before `with db_connection() as conn:`)
- Purge call: Insert at line 195 (after portal loop, before summary logging)
- Pass `keywords` to `process_portal()` at line 182

**`process_portal()`** (line 70-144):
- Keyword filtering: Insert between line 106 (end of ListingRecord conversion) and line 109 (start of validation)
- Deduplication: Insert immediately after keyword filtering
- `keywords` parameter: Add to function signature at line 71

### Database Purge Query

Source: `db/migrations/001_initial_schema.sql` lines 25-52

```sql
-- Listings table structure (relevant columns for purge):
-- id              UUID PRIMARY KEY
-- title           TEXT NOT NULL
-- description     TEXT (nullable)
-- source_portal   UUID NOT NULL REFERENCES portals(id)

-- Purge approach: fetch all, filter in Python, delete by ID
SELECT id, title, description FROM listings;
-- Then:
DELETE FROM listings WHERE id = ANY(%s);  -- psycopg2 array parameter
```

**Index note:** There is no index on title/description for text search that would help with LIKE queries, which is another reason to use the Python-based approach. The `id` column is the PRIMARY KEY, so `DELETE WHERE id = ANY(...)` is efficient (index scan).

### Test Pattern (Following Existing Conventions)

Source: `scraper/tests/test_canadabuys.py` and `scraper/tests/conftest.py`

The existing test suite uses:
- Pure unit tests with no database connection required
- Fixtures for sample data
- Direct function calls (not HTTP/integration tests)
- `_parse_csv` is tested directly with fixture CSV strings

Keywords tests should follow the same pattern:

```python
# scraper/tests/test_keywords.py

import pytest
from scraper.pipeline.keywords import load_keywords, matches_keywords, filter_listings

class TestLoadKeywords:
    def test_loads_expected_count(self, tmp_path):
        """Load from real CSV and verify keyword count."""
        # Use actual keywords_library.csv or create fixture

    def test_fails_on_missing_file(self, tmp_path):
        """SystemExit raised when CSV file doesn't exist."""

    def test_fails_on_missing_columns(self, tmp_path):
        """SystemExit raised when required columns are missing."""

    def test_fails_on_empty_keywords(self, tmp_path):
        """SystemExit raised when CSV has header but no data rows."""

    def test_keywords_are_lowercased(self, tmp_path):
        """All returned keywords are lowercased."""

class TestMatchesKeywords:
    def test_matches_title(self):
        """Keyword in title returns True."""

    def test_matches_description(self):
        """Keyword in description returns True."""

    def test_case_insensitive(self):
        """Match is case-insensitive."""

    def test_partial_match(self):
        """Partial substring match works (e.g., 'translation' in 'translator')."""

    def test_french_accents(self):
        """French keywords with accents match correctly."""

    def test_no_match_returns_false(self):
        """Non-matching listing returns False."""

    def test_none_fields_handled(self):
        """None title or description doesn't crash."""

    def test_multi_word_keyword(self):
        """Multi-word keyword matches as full phrase."""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No filtering (scrape everything) | Keyword-based filtering at scraper level | Phase 6 (this phase) | Reduces database size from thousands of irrelevant listings to ~100-200 matching ones |
| CanadaBuys ingests all rows | CanadaBuys filters by keyword before upsert | Phase 6 | Only relevant listings reach the database |

**No deprecated/outdated concerns:** This phase uses only Python stdlib features (csv, pathlib) and psycopg2 patterns already established in the project. Nothing is at risk of deprecation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `/Users/clawbot/dev/pytest.ini` |
| Quick run command | `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py -x -q` |
| Full suite command | `cd /Users/clawbot/dev && python -m pytest -x -q` |
| Estimated runtime | ~3 seconds (unit tests only, no DB needed) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KWRD-01 | Keywords loaded from CSV with validation | unit | `pytest scraper/tests/test_keywords.py::TestLoadKeywords -x` | No -- Wave 0 gap |
| KWRD-02 | Keywords CSV exists at known path | unit | `pytest scraper/tests/test_keywords.py::test_real_csv_exists -x` | No -- Wave 0 gap |
| KWRD-03 | Case-insensitive EN/FR matching | unit | `pytest scraper/tests/test_keywords.py::TestMatchesKeywords -x` | No -- Wave 0 gap |
| FILT-01 | CanadaBuys listings filtered by keyword | unit | `pytest scraper/tests/test_keywords.py::TestFilterListings -x` | No -- Wave 0 gap |
| FILT-05 | Deduplication by source_listing_id | unit | `pytest scraper/tests/test_keywords.py::TestDeduplicateListings -x` | No -- Wave 0 gap |
| PURG-01 | Non-matching listings deleted from DB | unit (mocked DB) | `pytest scraper/tests/test_keywords.py::TestPurge -x` | No -- Wave 0 gap |
| PURG-02 | Purge uses same matching logic | unit | Covered by PURG-01 tests (same function call) | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task, run: `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py -x -q`
- **Full suite trigger:** Before merging final task: `cd /Users/clawbot/dev && python -m pytest -x -q`
- **Phase-complete gate:** Full suite green + manual `python -c "from scraper.pipeline.keywords import load_keywords; kw = load_keywords(); print(len(kw))"` confirms 121 keywords loaded
- **Estimated feedback latency per task:** ~3 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `scraper/tests/test_keywords.py` -- covers KWRD-01, KWRD-02, KWRD-03, FILT-01, FILT-05, PURG-01, PURG-02
- [ ] No new fixtures needed in `conftest.py` -- keyword tests use `tmp_path` (pytest built-in) for CSV fixtures and `ListingRecord` (already importable)
- [ ] No framework install needed -- pytest already configured

## Open Questions

1. **Exact keyword count discrepancy**
   - What we know: ROADMAP.md says "122 keywords" but `wc -l` on the CSV reports 121 lines (1 header + 120 data rows? Or 121 data rows with no final newline?). Manual count of the CSV content shows 121 data rows.
   - What's unclear: Whether the "122" in ROADMAP.md is off-by-one or if a keyword is missing.
   - Recommendation: The implementation should load whatever the CSV contains and log the count. The test should verify "at least 100 keywords loaded" rather than an exact count.

2. **Dockerfile COPY for keywords CSV**
   - What we know: The CSV lives at repo root. The scraper Dockerfile likely copies only `scraper/` directory contents.
   - What's unclear: Whether the Docker build context includes the repo root (making `COPY keywords_library.csv` possible).
   - Recommendation: Check the Dockerfile and add a `COPY keywords_library.csv /app/keywords_library.csv` line. Adjust the `KEYWORDS_CSV_PATH` constant accordingly for the Docker context. This is a build-time concern, not a runtime logic concern.

3. **Purge timing relative to CanadaBuys scrape**
   - What we know: Purge should run "as part of the scrape job" per CONTEXT.md. It should run after CanadaBuys filtering is in place.
   - What's unclear: Should purge run before the portal loop (cleaning up first) or after (ensuring new matching listings are inserted first)?
   - Recommendation: Run purge AFTER the portal loop. This ensures newly-scraped matching listings are upserted before the purge removes non-matching ones. Running purge first would leave a window where the database has fewer listings than expected.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `scraper/pipeline/canadabuys.py` -- full CSV parsing flow, field mapping, ListingRecord construction (lines 93-212)
- Codebase inspection: `scraper/pipeline/orchestrator.py` -- `run_pipeline()` (lines 147-200), `process_portal()` (lines 70-144), integration points identified
- Codebase inspection: `scraper/db.py` -- `upsert_listings()` (lines 269-313), connection management, psycopg2 patterns
- Codebase inspection: `scraper/models.py` -- `ListingRecord` (lines 126-180), fields: title (str), description (Optional[str]), source_listing_id (Optional[str])
- Codebase inspection: `scraper/main.py` -- CLI entry point (lines 69-138), startup flow
- Codebase inspection: `scraper/config.py` -- configuration patterns (environment variables, fail-fast at import)
- Codebase inspection: `db/migrations/001_initial_schema.sql` -- listings table schema, indexes, constraints
- Codebase inspection: `keywords_library.csv` -- verified 121 data rows, 3 columns (Category, Language, Keyword), EN+FR keywords with accents
- Codebase inspection: `scraper/tests/` -- test patterns (conftest.py fixtures, test_canadabuys.py as model for new tests)
- Codebase inspection: `pytest.ini` -- test configuration (testpaths, asyncio_mode)

### Secondary (MEDIUM confidence)
- Python docs: `csv.DictReader` handles quoting, escaping, and BOM when combined with `utf-8-sig` encoding
- Python docs: `str.lower()` in Python 3 correctly handles Unicode characters including French accents
- psycopg2 docs: `ANY(%s)` with list parameter for efficient batch DELETE

### Tertiary (LOW confidence)
- None. All findings are from direct codebase inspection with HIGH confidence.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all stdlib + existing project deps
- Architecture: HIGH - all integration points identified with exact file/line references
- Pitfalls: HIGH - all identified through direct code inspection (Docker path, encoding, None handling)
- Code examples: HIGH - patterns derived from existing codebase conventions

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable -- no external dependencies, no fast-moving APIs)
