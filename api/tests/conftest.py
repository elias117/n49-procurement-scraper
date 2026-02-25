"""Shared test fixtures for the search API."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_connection():
    """Mock psycopg2 connection with cursor context manager."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_conn._mock_cursor = mock_cursor
    return mock_conn


@pytest.fixture
def sample_portal_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_listing_row(sample_portal_id):
    """A dict mimicking a RealDictCursor row from the listings table."""
    return {
        "id": str(uuid.uuid4()),
        "title": "IT Infrastructure Modernization Services",
        "description": "Cloud migration and server consolidation for federal departments.",
        "source_portal": sample_portal_id,
        "portal_name": "CanadaBuys",
        "closing_date": datetime.now(timezone.utc) + timedelta(days=30),
        "province": "Ontario",
        "value_min": 500000.0,
        "value_max": 2000000.0,
        "posting_date": datetime.now(timezone.utc) - timedelta(days=5),
        "classification_codes": [
            {"system": "GSIN", "code": "N7030", "description": "IT Equipment"},
        ],
        "snippet": "Cloud migration and <mark>server</mark> consolidation...",
        "rrf_score": 0.032,
    }


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client returning a fixed embedding vector."""
    mock_client = MagicMock()
    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = [0.1] * 1536
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [mock_embedding_data]
    mock_client.embeddings.create.return_value = mock_embedding_response
    return mock_client
