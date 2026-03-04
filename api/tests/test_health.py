"""Tests for health endpoint."""
from unittest.mock import patch, MagicMock


def test_health_returns_200(client):
    """Health endpoint returns 200 with listing count."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = (897,)
    mock_conn.cursor.return_value = mock_cursor

    with patch("api.routers.health.get_connection", return_value=mock_conn):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["listings_count"] == 897
    mock_conn.close.assert_called_once()


def test_health_db_error(client):
    """Health endpoint returns unhealthy on DB error."""
    with patch("api.routers.health.get_connection", side_effect=Exception("conn failed")):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"


def test_health_closes_connection_on_query_error(client):
    """Connection should still close if cursor/query work fails."""
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("query failed")

    with patch("api.routers.health.get_connection", return_value=mock_conn):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "unhealthy"
    mock_conn.close.assert_called_once()
