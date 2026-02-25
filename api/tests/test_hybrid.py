"""Unit tests for RRF hybrid search logic."""
from unittest.mock import MagicMock, patch

from api.models.request import SearchRequest
from api.search.hybrid import (
    _calculate_offset,
    _calculate_oversample,
    execute_hybrid_search,
)


def _make_mock_conn(rows=None):
    """Create a mock psycopg2 connection with RealDictCursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows or []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def test_hybrid_search_builds_correct_sql():
    """Full hybrid search SQL contains keyword, semantic, RRF components."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="IT consulting", page_size=25, page=1)
    query_embedding = [0.1] * 1536

    execute_hybrid_search(
        mock_conn, params, query_embedding, "TRUE", {}
    )

    # Get the SQL that was executed
    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]
    sql_params = call_args[0][1]

    assert "keyword_search" in sql
    assert "semantic_search" in sql
    assert "rrf_score" in sql
    assert "FULL OUTER JOIN" in sql
    assert "total_count" in sql

    assert sql_params["query"] == "IT consulting"
    assert sql_params["query_embedding"] == query_embedding
    assert "rrf_k" in sql_params
    assert "oversample" in sql_params
    assert "page_size" in sql_params
    assert "offset" in sql_params


def test_empty_query_skips_search_ctes():
    """Browse mode (empty query) should not use keyword or semantic CTEs."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="", page_size=25, page=1)

    execute_hybrid_search(mock_conn, params, None, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]

    assert "keyword_search" not in sql
    assert "semantic_search" not in sql
    # Should still have filtered CTE and pagination
    assert "filtered" in sql
    assert "LIMIT" in sql


def test_none_embedding_falls_back_keyword_only():
    """None embedding should fall back to keyword-only search."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="IT consulting", page_size=25, page=1)

    execute_hybrid_search(mock_conn, params, None, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]

    assert "keyword_search" in sql
    assert "semantic_search" not in sql
    assert "websearch_to_tsquery" in sql


def test_oversample_calculation():
    """Oversample should be page_size * factor, capped at 100."""
    # page_size=25, factor=4 -> 100
    assert _calculate_oversample(25) == 100
    # page_size=50, factor=4 -> capped at 100
    assert _calculate_oversample(50) == 100
    # page_size=10, factor=4 -> 40
    assert _calculate_oversample(10) == 40


def test_offset_calculation():
    """Offset should be (page - 1) * page_size."""
    assert _calculate_offset(1, 25) == 0
    assert _calculate_offset(3, 25) == 50
    assert _calculate_offset(2, 10) == 10


@patch("api.search.hybrid.config")
def test_rrf_k_from_config(mock_config):
    """RRF k parameter should come from config."""
    mock_config.RRF_K = 60
    mock_config.RRF_OVERSAMPLE_FACTOR = 4
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    params = SearchRequest(q="test query", page_size=25, page=1)
    query_embedding = [0.1] * 1536

    execute_hybrid_search(mock_conn, params, query_embedding, "TRUE", {})

    call_args = mock_cursor.execute.call_args
    sql_params = call_args[0][1]

    assert sql_params["rrf_k"] == 60
