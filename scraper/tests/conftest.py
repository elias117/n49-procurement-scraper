"""
Shared test fixtures for the scraper pipeline.

All fixtures use mocked database connections -- no real DB required.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_listing_dict():
    """
    A fully populated listing dict with realistic Canadian procurement data.
    """
    return {
        "title": "IT Infrastructure Modernization Services",
        "description": (
            "The Government of Canada is seeking qualified vendors to provide "
            "IT infrastructure modernization services including cloud migration, "
            "server consolidation, and network upgrades for federal departments."
        ),
        "reference_number": "EN578-200001/A",
        "posting_date": "2026-02-01",
        "closing_date": "2026-03-15",
        "status": "open",
        "value_min": 500000.00,
        "value_max": 2000000.00,
        "contact_name": "Jane Smith",
        "contact_email": "jane.smith@tpsgc-pwgsc.gc.ca",
        "contact_phone": "613-555-0123",
        "source_url": "https://canadabuys.canada.ca/en/tender-opportunities/12345",
        "source_listing_id": "PW-$$WN-001-78945",
        "classification_codes": [
            {"system": "GSIN", "code": "N7030", "description": "IT Equipment"},
            {"system": "NAICS", "code": "541512", "description": "Computer Systems Design"},
        ],
        "province": "Ontario",
        "raw_location": "National Capital Region (NCR), Ottawa, ON",
        "documents": [
            {
                "name": "Statement of Work",
                "type": "pdf",
                "url": "https://canadabuys.canada.ca/docs/sow-12345.pdf",
                "date": "2026-02-01",
            },
            {
                "name": "Evaluation Criteria",
                "type": "pdf",
                "url": "https://canadabuys.canada.ca/docs/eval-12345.pdf",
                "date": "2026-02-01",
            },
        ],
    }


@pytest.fixture
def sample_listing_minimal():
    """
    A minimal listing dict with only the required fields.
    """
    return {
        "title": "Office Supplies Procurement",
        "source_url": "https://example.com/listing/999",
        "source_portal": str(uuid.uuid4()),
    }


@pytest.fixture
def sample_portal_dict():
    """
    A dict matching PortalRecord fields.
    """
    return {
        "id": str(uuid.uuid4()),
        "name": "CanadaBuys",
        "url": "https://canadabuys.canada.ca/en/tender-opportunities",
        "level": "federal",
        "province": None,
        "language": "both",
        "requires_login": False,
        "enabled": True,
    }


@pytest.fixture
def mock_db_connection():
    """
    A mock psycopg2 connection with mock cursor.

    Supports execute, execute_values, fetchall, fetchone, and context manager.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Make cursor work as a context manager
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    # Make conn.cursor() return the mock cursor
    mock_conn.cursor.return_value = mock_cursor

    # Store cursor for test assertions
    mock_conn._mock_cursor = mock_cursor

    return mock_conn


@pytest.fixture
def sample_html_content():
    """
    A realistic HTML snippet of a procurement listing page with 3 listings.
    For use in extraction tests in later plans.
    """
    return """
    <html>
    <body>
    <table class="listing-table">
        <thead>
            <tr>
                <th>Reference</th><th>Title</th><th>Closing Date</th><th>Status</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>RFP-2026-001</td>
                <td><a href="/listing/001">Network Equipment Supply and Installation</a></td>
                <td>March 30, 2026</td>
                <td>Open</td>
            </tr>
            <tr>
                <td>RFP-2026-002</td>
                <td><a href="/listing/002">Building Maintenance Services - Downtown Campus</a></td>
                <td>April 15, 2026</td>
                <td>Open</td>
            </tr>
            <tr>
                <td>RFP-2026-003</td>
                <td><a href="/listing/003">Professional Consulting Services for Environmental Assessment</a></td>
                <td>March 22, 2026</td>
                <td>Open</td>
            </tr>
        </tbody>
    </table>
    </body>
    </html>
    """


@pytest.fixture
def mock_openai_client():
    """
    Mock OpenAI client that returns predefined embedding vectors
    and extraction responses. For use in later plans.
    """
    mock_client = MagicMock()

    # Mock embedding response
    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = [0.1] * 1536
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [mock_embedding_data]
    mock_client.embeddings.create.return_value = mock_embedding_response

    return mock_client
