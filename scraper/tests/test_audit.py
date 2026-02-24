"""
Tests for the audit logging module.

All tests use mocked DB functions -- no real database required.
"""

from unittest.mock import MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.audit import start_run, complete_run, fail_run


@pytest.fixture
def portal():
    """A test PortalRecord."""
    return PortalRecord(
        id="test-portal-id-123",
        name="TestPortal",
        url="https://example.com/procurement",
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def mock_conn():
    """A mock DB connection."""
    return MagicMock()


class TestStartRun:
    @patch("scraper.pipeline.audit.db")
    def test_start_run_calls_db(self, mock_db, mock_conn, portal):
        """start_run calls db.start_scrape_run with the portal ID."""
        mock_db.start_scrape_run.return_value = "run-id-abc"

        result = start_run(mock_conn, portal)

        mock_db.start_scrape_run.assert_called_once_with(
            mock_conn, "test-portal-id-123"
        )
        assert result == "run-id-abc"

    @patch("scraper.pipeline.audit.db")
    def test_start_run_returns_run_id(self, mock_db, mock_conn, portal):
        """start_run returns the run_id from db.start_scrape_run."""
        mock_db.start_scrape_run.return_value = "unique-run-id"

        run_id = start_run(mock_conn, portal)

        assert run_id == "unique-run-id"


class TestCompleteRun:
    @patch("scraper.pipeline.audit.db")
    def test_complete_run_calls_db(self, mock_db, mock_conn, portal):
        """complete_run calls db.complete_scrape_run with stats."""
        stats = {"found": 10, "new": 5, "updated": 3}

        complete_run(mock_conn, "run-123", portal, stats)

        mock_db.complete_scrape_run.assert_called_once_with(
            mock_conn, "run-123", stats
        )

    @patch("scraper.pipeline.audit.db")
    def test_complete_run_logs_stats(self, mock_db, mock_conn, portal, caplog):
        """complete_run logs the stats summary."""
        stats = {"found": 10, "new": 5, "updated": 3}

        import logging
        with caplog.at_level(logging.INFO, logger="scraper.audit"):
            complete_run(mock_conn, "run-123", portal, stats)

        assert "TestPortal" in caplog.text
        assert "10 found" in caplog.text
        assert "5 new" in caplog.text
        assert "3 updated" in caplog.text


class TestFailRun:
    @patch("scraper.pipeline.audit.db")
    def test_fail_run_calls_db(self, mock_db, mock_conn, portal):
        """fail_run calls db.fail_scrape_run with error message."""
        error = RuntimeError("Connection timeout")

        fail_run(mock_conn, "run-456", portal, error)

        mock_db.fail_scrape_run.assert_called_once_with(
            mock_conn, "run-456", "Connection timeout"
        )

    @patch("scraper.pipeline.audit.db")
    def test_fail_run_checks_auto_disable(self, mock_db, mock_conn, portal):
        """fail_run calls db.check_auto_disable after failure."""
        error = RuntimeError("Connection timeout")
        mock_db.check_auto_disable.return_value = False

        fail_run(mock_conn, "run-456", portal, error)

        mock_db.check_auto_disable.assert_called_once_with(
            mock_conn, "test-portal-id-123"
        )

    @patch("scraper.pipeline.audit.db")
    def test_fail_run_logs_when_portal_disabled(
        self, mock_db, mock_conn, portal, caplog
    ):
        """fail_run logs a warning when auto-disable triggers."""
        error = RuntimeError("Connection timeout")
        mock_db.check_auto_disable.return_value = True

        import logging
        with caplog.at_level(logging.WARNING, logger="scraper.audit"):
            fail_run(mock_conn, "run-456", portal, error)

        assert "auto-disabled" in caplog.text.lower()
