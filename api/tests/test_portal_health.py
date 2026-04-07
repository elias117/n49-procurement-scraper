"""Tests for portal health and data freshness router endpoints."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid


def _mock_portal_health_db(rows):
    """Create db_connection context and cursor returning the given rows."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value = mock_cursor

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


def _mock_freshness_db(row):
    """Create db_connection context and cursor returning a single row."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = row
    mock_conn.cursor.return_value = mock_cursor

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


# ---------------------------------------------------------------------------
# /health/portals
# ---------------------------------------------------------------------------


def test_portal_health_returns_list(client):
    """GET /health/portals returns a list of portal health entries."""
    portal_id = uuid.uuid4()
    now = datetime(2026, 3, 30, 5, 0, tzinfo=timezone.utc)
    rows = [
        {
            "portal_id": str(portal_id),
            "name": "CanadaBuys",
            "url": "https://canadabuys.canada.ca",
            "level": "federal",
            "province": None,
            "enabled": True,
            "recent_failures": 0,
            "recent_total": 5,
            "last_success_at": now,
            "last_run_at": now,
            "latest_completed_listings_found": 42,
            "historical_nonzero_runs": 7,
            "zero_result_regression": False,
            "last_run_status": "completed",
            "listings_found": 42,
            "listings_new": 3,
            "listings_updated": 39,
            "duration_seconds": 12.5,
            "error_message": None,
            "total_listings": 150,
        }
    ]

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_portal_health_db(rows),
    ):
        response = client.get("/health/portals")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "CanadaBuys"
    assert data[0]["enabled"] is True
    assert data[0]["recent_failures"] == 0
    assert data[0]["listings_found"] == 42
    assert data[0]["latest_completed_listings_found"] == 42
    assert data[0]["historical_nonzero_runs"] == 7
    assert data[0]["zero_result_regression"] is False
    assert data[0]["total_listings"] == 150


def test_portal_health_empty_portals(client):
    """GET /health/portals returns empty list when no portals exist."""
    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_portal_health_db([]),
    ):
        response = client.get("/health/portals")

    assert response.status_code == 200
    assert response.json() == []


def test_portal_health_multiple_portals(client):
    """GET /health/portals returns all portals ordered by name."""
    now = datetime(2026, 3, 30, 5, 0, tzinfo=timezone.utc)
    rows = [
        {
            "portal_id": str(uuid.uuid4()),
            "name": "BidsAndTenders - Alberta",
            "url": "https://alberta.bidsandtenders.ca",
            "level": "provincial",
            "province": "AB",
            "enabled": True,
            "recent_failures": 2,
            "recent_total": 5,
            "last_success_at": now,
            "last_run_at": now,
            "latest_completed_listings_found": 10,
            "historical_nonzero_runs": 4,
            "zero_result_regression": False,
            "last_run_status": "completed",
            "listings_found": 10,
            "listings_new": 1,
            "listings_updated": 9,
            "duration_seconds": 8.3,
            "error_message": None,
            "total_listings": 25,
        },
        {
            "portal_id": str(uuid.uuid4()),
            "name": "CanadaBuys",
            "url": "https://canadabuys.canada.ca",
            "level": "federal",
            "province": None,
            "enabled": True,
            "recent_failures": 0,
            "recent_total": 5,
            "last_success_at": now,
            "last_run_at": now,
            "latest_completed_listings_found": 42,
            "historical_nonzero_runs": 12,
            "zero_result_regression": False,
            "last_run_status": "completed",
            "listings_found": 42,
            "listings_new": 3,
            "listings_updated": 39,
            "duration_seconds": 12.5,
            "error_message": None,
            "total_listings": 150,
        },
    ]

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_portal_health_db(rows),
    ):
        response = client.get("/health/portals")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "BidsAndTenders - Alberta"
    assert data[1]["name"] == "CanadaBuys"


def test_portal_health_disabled_portal(client):
    """GET /health/portals includes disabled portals with enabled=False."""
    rows = [
        {
            "portal_id": str(uuid.uuid4()),
            "name": "MERX",
            "url": "https://merx.com",
            "level": "national",
            "province": None,
            "enabled": False,
            "recent_failures": 5,
            "recent_total": 5,
            "last_success_at": None,
            "last_run_at": None,
            "latest_completed_listings_found": None,
            "historical_nonzero_runs": 0,
            "zero_result_regression": False,
            "last_run_status": None,
            "listings_found": None,
            "listings_new": None,
            "listings_updated": None,
            "duration_seconds": None,
            "error_message": "Timeout after 30s",
            "total_listings": 0,
        }
    ]

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_portal_health_db(rows),
    ):
        response = client.get("/health/portals")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["enabled"] is False
    assert data[0]["recent_failures"] == 5
    assert data[0]["error_message"] == "Timeout after 30s"


def test_portal_health_failed_last_run(client):
    """GET /health/portals shows error_message for failed last run."""
    rows = [
        {
            "portal_id": str(uuid.uuid4()),
            "name": "SEAO",
            "url": "https://seao.ca",
            "level": "provincial",
            "province": "QC",
            "enabled": True,
            "recent_failures": 1,
            "recent_total": 5,
            "last_success_at": datetime(2026, 3, 29, 5, 0, tzinfo=timezone.utc),
            "last_run_at": datetime(2026, 3, 30, 5, 0, tzinfo=timezone.utc),
            "latest_completed_listings_found": 24,
            "historical_nonzero_runs": 9,
            "zero_result_regression": False,
            "last_run_status": "failed",
            "listings_found": None,
            "listings_new": None,
            "listings_updated": None,
            "duration_seconds": 2.1,
            "error_message": "HTTP 502 from SEAO API",
            "total_listings": 80,
        }
    ]

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_portal_health_db(rows),
    ):
        response = client.get("/health/portals")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["last_run_status"] == "failed"
    assert data[0]["error_message"] == "HTTP 502 from SEAO API"
    assert data[0]["latest_completed_listings_found"] == 24
    assert data[0]["historical_nonzero_runs"] == 9
    assert data[0]["zero_result_regression"] is False
    assert data[0]["total_listings"] == 80


def test_portal_health_zero_result_regression(client):
    """GET /health/portals flags regression when latest completed run has 0 listings."""
    rows = [
        {
            "portal_id": str(uuid.uuid4()),
            "name": "BC Bid",
            "url": "https://www.bcbid.gov.bc.ca",
            "level": "provincial",
            "province": "BC",
            "enabled": True,
            "recent_failures": 0,
            "recent_total": 5,
            "last_success_at": datetime(2026, 4, 1, 5, 0, tzinfo=timezone.utc),
            "last_run_at": datetime(2026, 4, 2, 5, 0, tzinfo=timezone.utc),
            "latest_completed_listings_found": 0,
            "historical_nonzero_runs": 11,
            "zero_result_regression": True,
            "last_run_status": "completed",
            "listings_found": 0,
            "listings_new": 0,
            "listings_updated": 0,
            "duration_seconds": 9.4,
            "error_message": None,
            "total_listings": 330,
        }
    ]

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_portal_health_db(rows),
    ):
        response = client.get("/health/portals")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["latest_completed_listings_found"] == 0
    assert data[0]["historical_nonzero_runs"] == 11
    assert data[0]["zero_result_regression"] is True


# ---------------------------------------------------------------------------
# /health/freshness
# ---------------------------------------------------------------------------


def test_data_freshness_returns_timestamp(client):
    """GET /health/freshness returns the most recent completed run timestamp."""
    last_updated = datetime(2026, 3, 30, 4, 30, tzinfo=timezone.utc)
    row = {"last_updated": last_updated}

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_freshness_db(row),
    ):
        response = client.get("/health/freshness")

    assert response.status_code == 200
    data = response.json()
    assert data["last_updated"] == last_updated.isoformat()


def test_data_freshness_no_completed_runs(client):
    """GET /health/freshness returns null when no completed runs exist."""
    row = {"last_updated": None}

    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_freshness_db(row),
    ):
        response = client.get("/health/freshness")

    assert response.status_code == 200
    data = response.json()
    assert data["last_updated"] is None


def test_data_freshness_no_rows(client):
    """GET /health/freshness handles edge case of empty scrape_runs table."""
    with patch(
        "api.routers.portal_health.db_connection",
        return_value=_mock_freshness_db(None),
    ):
        response = client.get("/health/freshness")

    assert response.status_code == 200
    data = response.json()
    assert data["last_updated"] is None
