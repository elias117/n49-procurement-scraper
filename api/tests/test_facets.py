"""Unit tests for facet count queries."""
from unittest.mock import MagicMock, call

from api.models.response import FacetCounts
from api.search.facets import execute_facet_counts


def _make_mock_conn(rows=None):
    """Create a mock psycopg2 connection with RealDictCursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows or []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def test_facets_returns_province_counts():
    """Facets should return province counts sorted by count DESC."""
    rows = [
        {"facet_type": "province", "facet_value": "Ontario", "count": 42},
        {"facet_type": "province", "facet_value": "Quebec", "count": 18},
        {"facet_type": "province", "facet_value": "Alberta", "count": 7},
    ]
    mock_conn, mock_cursor = _make_mock_conn(rows)

    result = execute_facet_counts(mock_conn, "TRUE", {})

    assert isinstance(result, FacetCounts)
    assert len(result.provinces) == 3
    assert result.provinces[0].value == "Ontario"
    assert result.provinces[0].count == 42
    assert result.provinces[1].value == "Quebec"
    assert result.provinces[1].count == 18
    assert result.provinces[2].value == "Alberta"
    assert result.provinces[2].count == 7


def test_facets_returns_portal_counts():
    """Facets should return portal counts."""
    rows = [
        {"facet_type": "portal", "facet_value": "CanadaBuys", "count": 55},
        {"facet_type": "portal", "facet_value": "MERX", "count": 12},
    ]
    mock_conn, mock_cursor = _make_mock_conn(rows)

    result = execute_facet_counts(mock_conn, "TRUE", {})

    assert len(result.portals) == 2
    assert result.portals[0].value == "CanadaBuys"
    assert result.portals[0].count == 55
    assert result.portals[1].value == "MERX"
    assert result.portals[1].count == 12


def test_facets_null_province_becomes_national():
    """NULL province should appear as 'National' in the output.

    The SQL uses COALESCE(province, 'National'), so the mock returns
    'National' as the facet_value (matching real DB behavior).
    """
    rows = [
        {"facet_type": "province", "facet_value": "National", "count": 30},
        {"facet_type": "province", "facet_value": "Ontario", "count": 10},
    ]
    mock_conn, mock_cursor = _make_mock_conn(rows)

    result = execute_facet_counts(mock_conn, "TRUE", {})

    assert result.provinces[0].value == "National"
    assert result.provinces[0].count == 30


def test_facets_empty_result_set():
    """Empty result set should return FacetCounts with empty lists."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])

    result = execute_facet_counts(mock_conn, "TRUE", {})

    assert isinstance(result, FacetCounts)
    assert result.provinces == []
    assert result.portals == []


def test_facets_uses_same_filter_clause():
    """Facet query should use the provided filter clause and params."""
    mock_conn, mock_cursor = _make_mock_conn(rows=[])
    filter_clause = "(province = ANY(%(regions)s) OR province IS NULL)"
    filter_params = {"regions": ["Ontario", "Quebec"]}

    execute_facet_counts(mock_conn, filter_clause, filter_params)

    # Verify the SQL executed contains the filter clause
    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]
    params = call_args[0][1]

    assert filter_clause in sql
    assert params == filter_params
