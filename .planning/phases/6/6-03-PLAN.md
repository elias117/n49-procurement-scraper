---
phase: 6-keyword-infrastructure
plan: 03
type: execute
wave: 2
depends_on:
  - 6-01
  - 6-02
files_modified:
  - scraper/db.py
  - scraper/pipeline/orchestrator.py
  - scraper/tests/test_keywords.py
autonomous: true
requirements:
  - PURG-01
  - PURG-02

must_haves:
  truths:
    - "Non-matching listings are hard-DELETEd from the database"
    - "Purge uses the same matches_keywords() function as scraper filtering"
    - "Purge runs after the portal loop so new matching listings are upserted first"
    - "Purge operates on ALL listings in the database (cross-portal scope)"
    - "Purge count is logged for observability"
  artifacts:
    - path: "scraper/db.py"
      provides: "purge_unmatched_listings function"
      exports: ["purge_unmatched_listings"]
    - path: "scraper/tests/test_keywords.py"
      provides: "Purge unit tests with mocked DB"
      contains: "TestPurge"
  key_links:
    - from: "scraper/db.py"
      to: "scraper/pipeline/keywords.py"
      via: "imports matches_keywords for purge logic"
      pattern: "from scraper\\.pipeline\\.keywords import matches_keywords"
    - from: "scraper/pipeline/orchestrator.py"
      to: "scraper/db.py"
      via: "calls purge_unmatched_listings after portal loop"
      pattern: "purge_unmatched_listings"
---

<objective>
Implement the database purge function that deletes non-matching listings, add the purge call to the orchestrator, and write unit tests.

Purpose: This removes historical listings from the database that do not match any keyword, completing the data cleanup requirements. The purge reuses the same `matches_keywords()` function as the scraper filter (PURG-02), ensuring consistency.

Output: `purge_unmatched_listings()` in `scraper/db.py`, purge call wired into `run_pipeline()`, and purge tests in `scraper/tests/test_keywords.py`.
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
@.planning/phases/6/6-02-SUMMARY.md
@scraper/db.py
@scraper/pipeline/orchestrator.py
@scraper/pipeline/keywords.py
@scraper/tests/test_keywords.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add purge_unmatched_listings to db.py and wire into orchestrator</name>
  <files>scraper/db.py, scraper/pipeline/orchestrator.py</files>
  <action>
**1. Add `purge_unmatched_listings()` to `scraper/db.py`:**

Add a new section at the end of db.py (after the existing "Scrape run helpers" section) with a clear section header comment:

```python
# ---------------------------------------------------------------------------
# Keyword purge (PURG-01, PURG-02)
# ---------------------------------------------------------------------------


def purge_unmatched_listings(conn, keywords: list[str]) -> int:
    """
    Delete all listings that don't match any keyword on title or description.

    Uses the same matches_keywords() function as the scraper filter (PURG-02)
    to ensure consistent matching logic.

    Fetches all (id, title, description) from the listings table, applies
    matches_keywords() in Python, and batch-DELETEs non-matching rows by ID.

    Args:
        conn: psycopg2 connection (caller manages transaction).
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
        logger.info("Purge: all %d listings match keywords, nothing to delete", len(rows))
        return 0

    deleted = 0
    batch_size = 1000
    with conn.cursor() as cur:
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i:i + batch_size]
            cur.execute("DELETE FROM listings WHERE id = ANY(%s)", (batch,))
            deleted += cur.rowcount

    logger.info(
        "Purge: deleted %d non-matching listings out of %d total",
        deleted, len(rows),
    )
    return deleted
```

Add `import logging` and `logger = logging.getLogger("scraper.db")` at the top of the file if not already present. Check if there is already a logger -- the file currently imports `config` which has a logger, but `db.py` itself does not have its own logger. Add one.

Also add `purge_unmatched_listings` to the module's public API (it will be imported by orchestrator).

**2. Wire purge call into `run_pipeline()` in `scraper/pipeline/orchestrator.py`:**

Add the import of `purge_unmatched_listings` to the existing db imports at the top:

```python
from scraper.db import (
    db_connection,
    get_enabled_portals,
    get_portal_by_name,
    purge_unmatched_listings,
    upsert_listings,
)
```

In `run_pipeline()`, add the purge call AFTER the portal loop and BEFORE the summary logging. Place it inside the `with db_connection() as conn:` block so the DELETE is committed with the same transaction:

```python
        # ... after the for portal in portals loop ...

        # Purge non-matching listings from database (PURG-01)
        purged = purge_unmatched_listings(conn, keywords)
        logger.info("Purged %d non-matching listings from database", purged)

        # Log summary (existing code)
        total_found = sum(r.get("found", 0) for r in results.values())
        # ... rest of existing summary logging ...
```

Do NOT change any other part of `run_pipeline()` or `process_portal()`.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -c "from scraper.db import purge_unmatched_listings; print('Import OK')" && grep "purge_unmatched_listings" scraper/pipeline/orchestrator.py && echo "Wired in orchestrator"</automated>
    <manual>Verify purge function exists in db.py and is called from orchestrator after portal loop</manual>
  </verify>
  <done>
    - `purge_unmatched_listings(conn, keywords)` exists in `scraper/db.py`
    - It imports and uses `matches_keywords()` from `scraper.pipeline.keywords` (PURG-02)
    - It fetches all listings, applies matching in Python, batch-DELETEs non-matching IDs
    - Batch size is 1000 for DELETE operations
    - `run_pipeline()` calls purge after the portal loop, inside the db_connection context
    - Purge count is logged
  </done>
</task>

<task type="auto">
  <name>Task 2: Add purge unit tests to test_keywords.py</name>
  <files>scraper/tests/test_keywords.py</files>
  <action>
Add a `TestPurge` class to the existing `scraper/tests/test_keywords.py` file (append after the existing test classes).

The purge function uses a real database connection, so tests must mock the connection and cursor. Follow the pattern from `conftest.py`'s `mock_db_connection` fixture.

```python
class TestPurge:
    """Tests for purge_unmatched_listings()."""

    @pytest.fixture
    def mock_conn(self):
        """Mock psycopg2 connection with cursor context manager."""
        mock = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock.cursor.return_value = mock_cursor
        mock._mock_cursor = mock_cursor
        return mock
```

Import `from unittest.mock import MagicMock` and `from scraper.db import purge_unmatched_listings` at the top of the file.

**Tests to write:**

1. `test_purge_deletes_non_matching(self, mock_conn)`:
   - Set `mock_cursor.fetchall.return_value` to 3 rows: 2 matching ("translation services" in title), 1 not matching ("office furniture" in title)
   - Set `mock_cursor.rowcount = 1`
   - Call `purge_unmatched_listings(mock_conn, ["translation"])`
   - Assert `cur.execute` was called with `DELETE FROM listings WHERE id = ANY(%s)` containing the non-matching ID
   - Assert return value is 1

2. `test_purge_nothing_when_all_match(self, mock_conn)`:
   - Set fetchall to return rows that all contain "translation" in title
   - Call purge, assert return value is 0
   - Assert DELETE was NOT called (only SELECT was executed)

3. `test_purge_uses_matches_keywords(self, mock_conn)`:
   - Use `unittest.mock.patch("scraper.db.matches_keywords")` to verify the purge function calls the exact same `matches_keywords` function
   - Assert it was called once per row with (title, description, keywords) args

4. `test_purge_handles_none_description(self, mock_conn)`:
   - Set fetchall to return rows where description is None
   - Call purge -- should not crash (matches_keywords handles None)
   - Assert no exception raised

5. `test_purge_batches_deletes(self, mock_conn)`:
   - Set fetchall to return 2500 non-matching rows (use list comprehension with fake UUIDs)
   - Set `mock_cursor.rowcount = 1000` for first two calls, `500` for last
   - Call purge, assert DELETE was called 3 times (batches of 1000, 1000, 500)

Make sure the mock cursor setup correctly handles the two separate `with conn.cursor() as cur:` blocks in the purge function (one for SELECT, one for DELETE). The simplest approach: `mock_conn.cursor.return_value` returns the same mock cursor for all calls, and `fetchall` returns the test data on the first call.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py::TestPurge -x -q</automated>
    <manual>All purge tests pass, covering delete, no-op, None handling, and batch behavior</manual>
  </verify>
  <done>
    - TestPurge class exists with 5 tests
    - Tests verify: non-matching rows deleted, all-matching returns 0, matches_keywords reused, None description handled, batch DELETE in groups of 1000
    - All tests pass
    - Full test suite still passes: `python -m pytest -x -q`
  </done>
</task>

</tasks>

<verification>
1. `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py -x -q` -- all keyword + purge tests pass
2. `cd /Users/clawbot/dev && python -m pytest -x -q` -- full test suite passes
3. `cd /Users/clawbot/dev && python -c "from scraper.db import purge_unmatched_listings; print('purge function importable')"` -- import works
4. `cd /Users/clawbot/dev && grep 'purge_unmatched_listings' scraper/pipeline/orchestrator.py` -- wired in orchestrator
5. `cd /Users/clawbot/dev && grep 'matches_keywords' scraper/db.py` -- purge uses same matching function (PURG-02)
</verification>

<success_criteria>
- `purge_unmatched_listings()` exists in `scraper/db.py` and uses `matches_keywords()` from keywords module
- Purge fetches all listings, filters in Python, batch-DELETEs non-matching by ID
- Purge is called in `run_pipeline()` after the portal loop, inside the db_connection context
- 5 purge tests pass covering all behaviors
- Full test suite passes with no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/6/6-03-SUMMARY.md`
</output>
