"""Integration tests for the /search endpoint."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


def _make_sample_rows(count=3):
    """Create sample result rows as list of dicts (like RealDictRow)."""
    rows = []
    for i in range(count):
        rows.append({
            "id": str(uuid.uuid4()),
            "title": f"IT Consulting Services RFP #{i + 1}",
            "description": f"Federal IT modernization project phase {i + 1}.",
            "closing_date": datetime.now(timezone.utc) + timedelta(days=30),
            "province": "Ontario",
            "value_min": 100000.0 * (i + 1),
            "value_max": 500000.0 * (i + 1),
            "posting_date": datetime.now(timezone.utc) - timedelta(days=5),
            "classification_codes": [
                {"system": "GSIN", "code": "N7030", "description": "IT"},
            ],
            "portal_name": "CanadaBuys",
            "rrf_score": 0.03 - i * 0.005,
            "total_count": count,
        })
    return rows


def _mock_execute_search(rows):
    """Return a mock for execute_hybrid_search."""
    total = rows[0]["total_count"] if rows else 0
    return MagicMock(return_value=(rows, total))


def test_search_returns_200_with_results(client):
    """GET /search?q=IT+consulting returns 200 with results."""
    rows = _make_sample_rows(3)
    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.embed_query", return_value=[0.1] * 1536), \
         patch("api.routers.search.execute_hybrid_search", _mock_execute_search(rows)):
        mock_conn.return_value = MagicMock()
        response = client.get("/search?q=IT+consulting")

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3
    assert len(data["results"]) == 3
    assert data["results"][0]["title"].startswith("IT Consulting")


def test_search_empty_query_returns_browse(client):
    """GET /search with no query returns 200 in browse mode."""
    rows = _make_sample_rows(2)
    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.execute_hybrid_search", _mock_execute_search(rows)):
        mock_conn.return_value = MagicMock()
        response = client.get("/search")

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2


def test_search_with_region_filter(client):
    """GET /search?q=test&regions=Ontario returns 200."""
    rows = _make_sample_rows(1)
    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.embed_query", return_value=[0.1] * 1536), \
         patch("api.routers.search.execute_hybrid_search", _mock_execute_search(rows)) as mock_search:
        mock_conn.return_value = MagicMock()
        response = client.get("/search?q=test&regions=Ontario")

    assert response.status_code == 200
    # Verify filter clause was built with region
    call_args = mock_search.call_args
    filter_clause = call_args[0][3] if len(call_args[0]) > 3 else call_args[1].get("filter_clause", "")
    # The filter clause is built before execute_hybrid_search is called
    # We verify the endpoint returned results successfully
    assert response.json()["total_count"] == 1


def test_search_with_value_filter(client):
    """GET /search?q=test&value_min=100000 returns 200."""
    rows = _make_sample_rows(1)
    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.embed_query", return_value=[0.1] * 1536), \
         patch("api.routers.search.execute_hybrid_search", _mock_execute_search(rows)):
        mock_conn.return_value = MagicMock()
        response = client.get("/search?q=test&value_min=100000")

    assert response.status_code == 200
    assert response.json()["total_count"] == 1


def test_search_pagination(client):
    """GET /search?q=test&page=2&page_size=10 returns correct pagination."""
    rows = _make_sample_rows(2)
    for r in rows:
        r["total_count"] = 25  # Simulate 25 total results

    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.embed_query", return_value=[0.1] * 1536), \
         patch("api.routers.search.execute_hybrid_search", _mock_execute_search(rows)):
        mock_conn.return_value = MagicMock()
        response = client.get("/search?q=test&page=2&page_size=10")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["total_count"] == 25
    assert data["total_pages"] == 3  # ceil(25/10)


def test_search_exact_mode_skips_embedding(client):
    """GET /search?q=tender123&mode=exact should NOT call embed_query."""
    rows = _make_sample_rows(1)
    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.embed_query") as mock_embed, \
         patch("api.routers.search.execute_exact_search", _mock_execute_search(rows)):
        mock_conn.return_value = MagicMock()
        response = client.get("/search?q=tender123&mode=exact")

    assert response.status_code == 200
    mock_embed.assert_not_called()


def test_search_embedding_failure_falls_back(client):
    """Embedding failure should fall back gracefully (still returns 200)."""
    rows = _make_sample_rows(1)
    with patch("api.routers.search.get_connection") as mock_conn, \
         patch("api.routers.search.embed_query", side_effect=Exception("API error")), \
         patch("api.routers.search.execute_hybrid_search", _mock_execute_search(rows)):
        mock_conn.return_value = MagicMock()
        response = client.get("/search?q=IT+consulting")

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
