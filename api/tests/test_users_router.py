"""Tests for users/auth router endpoints."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid


def _mock_users_db(row):
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


def test_auth_verify_success(client):
    """Valid credentials return a non-sensitive user payload."""
    user_id = uuid.uuid4()
    visited_at = datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)
    row = {
        "id": user_id,
        "username": "alice",
        "name": "Alice Doe",
        "last_visited_at": visited_at,
    }

    with patch("api.routers.users.db_connection", return_value=_mock_users_db(row)):
        response = client.post(
            "/auth/verify",
            json={"username": "alice", "password": "secret"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user_id)
    assert data["username"] == "alice"
    assert data["name"] == "Alice Doe"
    assert data["last_visited_at"] == visited_at.isoformat()
    assert "password_hash" not in data


def test_auth_verify_invalid_credentials(client):
    """Invalid credentials return 401."""
    with patch("api.routers.users.db_connection", return_value=_mock_users_db(None)):
        response = client.post(
            "/auth/verify",
            json={"username": "alice", "password": "wrong"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_get_auth_user_not_found(client):
    """Unknown username should return 404."""
    with patch("api.routers.users.db_connection", return_value=_mock_users_db(None)):
        response = client.get("/auth/user", params={"username": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_get_last_visit_invalid_uuid_returns_422(client):
    """Path UUID validation should reject malformed values."""
    response = client.get("/users/not-a-uuid/last-visit")
    assert response.status_code == 422


def test_update_last_visit_success(client):
    """PUT last-visit updates and returns ISO timestamp."""
    visited_at = datetime(2026, 3, 3, 13, 45, tzinfo=timezone.utc)
    row = {"last_visited_at": visited_at}
    user_id = uuid.uuid4()

    with patch("api.routers.users.db_connection", return_value=_mock_users_db(row)):
        response = client.put(f"/users/{user_id}/last-visit")

    assert response.status_code == 200
    assert response.json()["last_visited_at"] == visited_at.isoformat()
