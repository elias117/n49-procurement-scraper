"""Unit tests for dynamic SQL filter construction."""
from datetime import datetime, timezone

from api.models.request import SearchRequest
from api.search.query_builder import build_filter_clause, build_sort_clause


def test_no_filters_default_open():
    """No params except defaults should include 48h closing_date guard."""
    params = SearchRequest()
    clause, sql_params = build_filter_clause(params)
    assert "closing_date > NOW() - INTERVAL '48 hours'" in clause
    assert "closing_date IS NULL" in clause
    assert sql_params == {}


def test_include_closed_removes_date_guard():
    """include_closed=True should NOT include the closing_date guard."""
    params = SearchRequest(include_closed=True)
    clause, sql_params = build_filter_clause(params)
    assert "closing_date > NOW()" not in clause
    assert clause == "TRUE"


def test_region_filter_includes_null():
    """Region filter should include NULL province (National/unspecified)."""
    params = SearchRequest(regions=["Ontario"], include_closed=True)
    clause, sql_params = build_filter_clause(params)
    assert "province = ANY(%(regions)s)" in clause
    assert "province IS NULL" in clause
    assert sql_params["regions"] == ["Ontario"]


def test_portal_filter():
    """Portal filter resolves portal names to IDs via subquery."""
    params = SearchRequest(
        portals=["CanadaBuys", "BC Bid"],
        include_closed=True,
    )
    clause, sql_params = build_filter_clause(params)
    assert "source_portal IN (SELECT id FROM portals WHERE name = ANY(%(portals)s))" in clause
    assert sql_params["portals"] == ["CanadaBuys", "BC Bid"]


def test_closing_date_range():
    """Both closing_date_from and closing_date_to produce range clauses."""
    dt_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dt_to = datetime(2026, 6, 30, tzinfo=timezone.utc)
    params = SearchRequest(
        closing_date_from=dt_from, closing_date_to=dt_to, include_closed=True
    )
    clause, sql_params = build_filter_clause(params)
    assert "closing_date >= %(closing_date_from)s" in clause
    assert "closing_date <= %(closing_date_to)s" in clause
    assert sql_params["closing_date_from"] == dt_from
    assert sql_params["closing_date_to"] == dt_to


def test_posting_date_range():
    """Both posting_date_from and posting_date_to produce range clauses."""
    dt_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dt_to = datetime(2026, 3, 31, tzinfo=timezone.utc)
    params = SearchRequest(
        posting_date_from=dt_from, posting_date_to=dt_to, include_closed=True
    )
    clause, sql_params = build_filter_clause(params)
    assert "posting_date >= %(posting_date_from)s" in clause
    assert "posting_date <= %(posting_date_to)s" in clause
    assert sql_params["posting_date_from"] == dt_from
    assert sql_params["posting_date_to"] == dt_to


def test_value_filter_excludes_nulls():
    """Value filter should include value_max IS NOT NULL."""
    params = SearchRequest(value_min=100000.0, include_closed=True)
    clause, sql_params = build_filter_clause(params)
    assert "value_max IS NOT NULL" in clause
    assert "value_max >= %(value_min)s" in clause
    assert sql_params["value_min"] == 100000.0


def test_value_filter_range_overlap():
    """Value range filter should use overlap logic."""
    params = SearchRequest(
        value_min=100000.0, value_max=500000.0, include_closed=True
    )
    clause, sql_params = build_filter_clause(params)
    assert "value_max IS NOT NULL" in clause
    assert "value_max >= %(value_min)s" in clause
    assert "value_min <= %(value_max)s" in clause
    assert sql_params["value_min"] == 100000.0
    assert sql_params["value_max"] == 500000.0


def test_classification_codes_filter():
    """Classification codes filter uses EXISTS subquery."""
    params = SearchRequest(
        classification_codes=["541512"], include_closed=True
    )
    clause, sql_params = build_filter_clause(params)
    assert "classification_codes IS NOT NULL" in clause
    assert "jsonb_array_elements" in clause
    assert "elem->>'code' = ANY(%(classification_codes)s)" in clause
    assert sql_params["classification_codes"] == ["541512"]


def test_combined_filters():
    """Multiple filters are AND-joined with correct params dict keys."""
    params = SearchRequest(
        regions=["Ontario", "Quebec"],
        value_min=100000.0,
        value_max=500000.0,
        include_closed=True,
    )
    clause, sql_params = build_filter_clause(params)
    # Should have region clause AND value clauses, joined with AND
    assert " AND " in clause
    assert "province = ANY(%(regions)s)" in clause
    assert "value_max >= %(value_min)s" in clause
    assert "regions" in sql_params
    assert "value_min" in sql_params
    assert "value_max" in sql_params


def test_sort_relevance():
    """sort_by='relevance' returns ORDER BY rrf_score DESC."""
    result = build_sort_clause("relevance", "asc")
    assert result == "ORDER BY rrf_score DESC"


def test_sort_posting_date_asc():
    """sort_by='posting_date', sort_order='asc' returns correct clause."""
    result = build_sort_clause("posting_date", "asc")
    assert result == "ORDER BY posting_date ASC NULLS LAST"


def test_sort_value_nulls_last():
    """sort_by='value' includes NULLS LAST."""
    result = build_sort_clause("value", "desc")
    assert "NULLS LAST" in result
    assert "value_max" in result
    assert "DESC" in result
