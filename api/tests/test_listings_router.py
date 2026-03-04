"""Tests for listing detail router endpoint."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import uuid


def _mock_listings_db(row):
    """Create db_connection context and cursor returning the given row."""
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


def test_get_listing_serializes_uuid_datetime_and_decimal(client):
    """Listing detail should JSON-serialize UUID/datetime/Decimal values."""
    listing_id = uuid.uuid4()
    portal_id = uuid.uuid4()
    now = datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc)

    row = {
        "id": listing_id,
        "source_portal": portal_id,
        "source_listing_id": "REF-123",
        "title": "IT Services",
        "description": "Desc",
        "status": "open",
        "language": "en",
        "posting_date": now,
        "closing_date": now,
        "amended_date": None,
        "province": "Ontario",
        "raw_location": None,
        "classification_codes": [],
        "value_min": Decimal("1000.50"),
        "value_max": Decimal("5000.00"),
        "contact_info": {"email": "test@example.com"},
        "documents": [],
        "revision": 1,
        "source_url": "https://example.com/listing?id=123",
        "last_scraped_at": now,
        "created_at": now,
        "updated_at": now,
        "source_portal_name": "CanadaBuys",
        "portal_url": "https://canadabuys.canada.ca",
    }

    with patch("api.routers.listings.db_connection", return_value=_mock_listings_db(row)):
        response = client.get(f"/listings/{listing_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(listing_id)
    assert data["source_portal"] == str(portal_id)
    assert data["posting_date"] == now.isoformat()
    assert data["value_min"] == 1000.5
    assert data["value_max"] == 5000.0


def test_get_listing_not_found_returns_404(client):
    """Unknown listing ID should return 404."""
    listing_id = uuid.uuid4()
    with patch("api.routers.listings.db_connection", return_value=_mock_listings_db(None)):
        response = client.get(f"/listings/{listing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Listing not found"


def test_get_listing_invalid_uuid_returns_422(client):
    """Path UUID validation should reject malformed IDs."""
    response = client.get("/listings/not-a-uuid")
    assert response.status_code == 422
