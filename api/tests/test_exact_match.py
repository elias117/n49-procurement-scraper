"""Unit tests for exact match search mode."""
from unittest.mock import MagicMock, patch

from api.models.request import SearchRequest
from api.search.hybrid import execute_exact_search


def _make_mock_conn(rows=None):
    """Create a mock psycopg2 connection with RealDictCursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows or []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def test_exact_match_uses_ilike():
    """Exact match SQL should contain ILIKE for pattern matching."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="EN578-200001", mode="exact", page_size=25, page=1)

    execute_exact_search(mock_conn, params, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]

    assert "ILIKE" in sql


def test_exact_match_searches_source_listing_id():
    """Exact match should search source_listing_id field."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="EN578-200001", mode="exact", page_size=25, page=1)

    execute_exact_search(mock_conn, params, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]

    assert "source_listing_id ILIKE" in sql


def test_exact_match_title_ranked_higher():
    """Title matches (rank 0) should be ranked before description matches (rank 2)."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="test tender", mode="exact", page_size=25, page=1)

    execute_exact_search(mock_conn, params, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]

    # Verify the CASE expression has title match as 0 and description as 2
    assert "WHEN title ILIKE" in sql
    assert "THEN 0" in sql
    assert "ELSE 2" in sql
    # Verify ordering by match_rank
    assert "ORDER BY m.match_rank" in sql


def test_exact_match_skips_embedding():
    """Exact match should not call embed_query -- no embedding needed."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="EN578-200001", mode="exact", page_size=25, page=1)

    with patch("api.search.hybrid.sanitize_snippet") as mock_sanitize:
        execute_exact_search(mock_conn, params, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql_params = call_args[0][1]

    # No embedding-related params should be present
    assert "query_embedding" not in sql_params
    assert "rrf_k" not in sql_params
    assert "oversample" not in sql_params


def test_exact_match_applies_filters():
    """Exact match should use the provided filter clause."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="test", mode="exact", page_size=25, page=1)
    filter_clause = "(province = ANY(%(regions)s) OR province IS NULL)"
    filter_params = {"regions": ["Ontario"]}

    execute_exact_search(mock_conn, params, filter_clause, filter_params)

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]
    sql_params = call_args[0][1]

    assert filter_clause in sql
    assert sql_params["regions"] == ["Ontario"]
