"""
Tests for database upsert logic in scraper/db.py.

All tests use mocked database connections -- no real DB required.
"""

import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from scraper.db import (
    UPSERT_SQL,
    upsert_listings,
    start_scrape_run,
    complete_scrape_run,
    fail_scrape_run,
    check_auto_disable,
)
from scraper.models import ListingRecord


# ---------------------------------------------------------------------------
# Helper to create ListingRecord instances for tests
# ---------------------------------------------------------------------------


def _make_listing(
    title="Test Listing",
    source_portal=None,
    source_listing_id=None,
    **kwargs,
):
    """Create a ListingRecord with sensible defaults for testing."""
    return ListingRecord(
        title=title,
        source_portal=source_portal or str(uuid.uuid4()),
        source_listing_id=source_listing_id or f"TEST-{uuid.uuid4().hex[:8]}",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# UPSERT SQL structure tests
# ---------------------------------------------------------------------------


class TestUpsertSql:
    """Tests for the UPSERT SQL string structure."""

    def test_upsert_sql_contains_on_conflict(self):
        """Verify the UPSERT_SQL string contains the ON CONFLICT clause."""
        assert "ON CONFLICT (source_portal, source_listing_id)" in UPSERT_SQL

    def test_upsert_sql_contains_do_update(self):
        """Verify the UPSERT_SQL contains DO UPDATE."""
        assert "DO UPDATE SET" in UPSERT_SQL

    def test_upsert_sql_increments_revision(self):
        """Verify revision counter is incremented on update."""
        assert "revision = listings.revision + 1" in UPSERT_SQL

    def test_upsert_sql_sets_last_scraped_at(self):
        """Verify last_scraped_at is updated on upsert."""
        assert "last_scraped_at = NOW()" in UPSERT_SQL


# ---------------------------------------------------------------------------
# upsert_listings function tests
# ---------------------------------------------------------------------------


class TestUpsertListings:
    """Tests for the upsert_listings function."""

    def test_upsert_empty_list_returns_zeros(self, mock_db_connection):
        """Call upsert_listings with empty list, verify returns zeros."""
        result = upsert_listings(mock_db_connection, str(uuid.uuid4()), [])
        assert result == {"found": 0, "new": 0, "updated": 0}

        # Cursor should not have been called
        mock_db_connection.cursor.assert_not_called()

    @patch("scraper.db.psycopg2.extras.execute_values")
    def test_upsert_calls_execute_values(self, mock_execute_values, mock_db_connection):
        """Mock the cursor, call with 2 listings, verify execute_values called."""
        portal_id = str(uuid.uuid4())
        listings = [
            _make_listing(
                title="Listing 1",
                source_portal=portal_id,
                source_listing_id="L-001",
            ),
            _make_listing(
                title="Listing 2",
                source_portal=portal_id,
                source_listing_id="L-002",
            ),
        ]

        # Setup mock cursor to return stats
        mock_cursor = mock_db_connection._mock_cursor
        mock_cursor.fetchone.return_value = {
            "total": 2,
            "new_count": 2,
            "updated_count": 0,
        }

        result = upsert_listings(mock_db_connection, portal_id, listings)

        # Verify execute_values was called
        mock_execute_values.assert_called_once()
        call_args = mock_execute_values.call_args

        # Verify the values list has 2 entries (one per listing)
        values_arg = call_args[0][2]  # Third positional arg is values
        assert len(values_arg) == 2

        # Verify result
        assert result == {"found": 2, "new": 2, "updated": 0}


# ---------------------------------------------------------------------------
# Scrape run helper tests
# ---------------------------------------------------------------------------


class TestScrapeRunHelpers:
    """Tests for start/complete/fail scrape run functions."""

    def test_start_scrape_run_inserts_running(self, mock_db_connection):
        """Mock cursor, verify INSERT contains status='running'."""
        mock_cursor = mock_db_connection._mock_cursor
        run_uuid = str(uuid.uuid4())
        mock_cursor.fetchone.return_value = (run_uuid,)

        portal_id = str(uuid.uuid4())
        result = start_scrape_run(mock_db_connection, portal_id)

        assert result == run_uuid
        # Verify execute was called with SQL containing 'running'
        execute_call = mock_cursor.execute.call_args
        sql = execute_call[0][0]
        assert "running" in sql.lower()
        assert "INSERT INTO scrape_runs" in sql
        # Verify portal_id is in params
        params = execute_call[0][1]
        assert portal_id in params

    def test_complete_scrape_run_updates_stats(self, mock_db_connection):
        """Mock cursor, verify UPDATE sets correct fields."""
        mock_cursor = mock_db_connection._mock_cursor
        run_id = str(uuid.uuid4())
        stats = {"found": 10, "new": 7, "updated": 3}

        complete_scrape_run(mock_db_connection, run_id, stats)

        execute_call = mock_cursor.execute.call_args
        sql = execute_call[0][0]
        assert "completed" in sql.lower()
        assert "listings_found" in sql
        assert "listings_new" in sql
        assert "listings_updated" in sql
        assert "duration_seconds" in sql

        params = execute_call[0][1]
        assert 10 in params  # found
        assert 7 in params   # new
        assert 3 in params   # updated
        assert run_id in params

    def test_fail_scrape_run_sets_error(self, mock_db_connection):
        """Mock cursor, verify error_message is set."""
        mock_cursor = mock_db_connection._mock_cursor
        run_id = str(uuid.uuid4())
        error_msg = "Connection timeout after 30s"

        fail_scrape_run(mock_db_connection, run_id, error_msg)

        execute_call = mock_cursor.execute.call_args
        sql = execute_call[0][0]
        assert "failed" in sql.lower()
        assert "error_message" in sql

        params = execute_call[0][1]
        assert error_msg in params
        assert run_id in params


# ---------------------------------------------------------------------------
# Auto-disable tests
# ---------------------------------------------------------------------------


class TestCheckAutoDisable:
    """Tests for the check_auto_disable function."""

    def test_check_auto_disable_triggers_after_5_failures(self, mock_db_connection):
        """Mock cursor to return 5 failed rows, verify disable_portal is called."""
        mock_cursor = mock_db_connection._mock_cursor
        portal_id = str(uuid.uuid4())

        # Return 5 rows all with status='failed'
        mock_cursor.fetchall.return_value = [
            {"status": "failed"},
            {"status": "failed"},
            {"status": "failed"},
            {"status": "failed"},
            {"status": "failed"},
        ]

        result = check_auto_disable(mock_db_connection, portal_id)

        assert result is True
        # Verify disable_portal was called (second execute call on the cursor)
        calls = mock_cursor.execute.call_args_list
        # First call is the SELECT, second should be the UPDATE for disable
        assert len(calls) >= 2
        disable_sql = calls[1][0][0]
        assert "enabled = false" in disable_sql.lower()

    def test_check_auto_disable_does_not_trigger_with_success(self, mock_db_connection):
        """Mock cursor to return 4 failed + 1 completed, verify disable NOT called."""
        mock_cursor = mock_db_connection._mock_cursor
        portal_id = str(uuid.uuid4())

        # Return 4 failed + 1 completed (most recent first)
        mock_cursor.fetchall.return_value = [
            {"status": "failed"},
            {"status": "failed"},
            {"status": "failed"},
            {"status": "failed"},
            {"status": "completed"},
        ]

        result = check_auto_disable(mock_db_connection, portal_id)

        assert result is False
        # Verify disable_portal was NOT called (only one execute call for SELECT)
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 1

    def test_check_auto_disable_not_enough_runs(self, mock_db_connection):
        """With fewer than 5 runs, auto-disable should not trigger."""
        mock_cursor = mock_db_connection._mock_cursor
        portal_id = str(uuid.uuid4())

        # Return only 3 failed runs
        mock_cursor.fetchall.return_value = [
            {"status": "failed"},
            {"status": "failed"},
            {"status": "failed"},
        ]

        result = check_auto_disable(mock_db_connection, portal_id)

        assert result is False
