"""Dynamic SQL filter and sort clause construction for search queries.

Builds parameterized WHERE and ORDER BY clauses from SearchRequest fields.
Uses %(param_name)s format for psycopg2 named parameters throughout.
"""
from api.models.request import SearchRequest


def build_filter_clause(params: SearchRequest) -> tuple[str, dict]:
    """Build a SQL WHERE fragment and params dict from search request filters.

    Returns:
        Tuple of (sql_where_string, params_dict) for psycopg2 parameterized execution.
        Returns ("TRUE", {}) if no filters are active.
    """
    clauses: list[str] = []
    sql_params: dict = {}

    # 1. Open listings guard (default: exclude closed, with 48h grace period)
    if not params.include_closed:
        clauses.append(
            "(closing_date > NOW() - INTERVAL '48 hours' OR closing_date IS NULL)"
        )

    # 2. Region filter (OR within, NULL province = National/unspecified = included)
    if params.regions:
        clauses.append(
            "(province = ANY(%(regions)s) OR province IS NULL)"
        )
        sql_params["regions"] = params.regions

    # 3. Portal filter (facets return portal names, resolve to IDs via subquery)
    if params.portals:
        clauses.append(
            "source_portal IN (SELECT id FROM portals WHERE name = ANY(%(portals)s))"
        )
        sql_params["portals"] = params.portals

    # 4. Closing date range
    if params.closing_date_from is not None:
        clauses.append("closing_date >= %(closing_date_from)s")
        sql_params["closing_date_from"] = params.closing_date_from
    if params.closing_date_to is not None:
        clauses.append("closing_date <= %(closing_date_to)s")
        sql_params["closing_date_to"] = params.closing_date_to

    # 5. Posting date range
    if params.posting_date_from is not None:
        clauses.append("posting_date >= %(posting_date_from)s")
        sql_params["posting_date_from"] = params.posting_date_from
    if params.posting_date_to is not None:
        clauses.append("posting_date <= %(posting_date_to)s")
        sql_params["posting_date_to"] = params.posting_date_to

    # 6. Contract value range (exclude NULL values when filter active)
    has_value_filter = params.value_min is not None or params.value_max is not None
    if has_value_filter:
        clauses.append("value_max IS NOT NULL")
    if params.value_min is not None:
        clauses.append("value_max >= %(value_min)s")
        sql_params["value_min"] = params.value_min
    if params.value_max is not None:
        clauses.append("value_min <= %(value_max)s")
        sql_params["value_max"] = params.value_max

    # 7. Classification codes (JSONB array search, exclude NULL classification)
    if params.classification_codes:
        clauses.append(
            "classification_codes IS NOT NULL AND EXISTS ("
            "SELECT 1 FROM jsonb_array_elements(classification_codes) elem "
            "WHERE elem->>'code' = ANY(%(classification_codes)s))"
        )
        sql_params["classification_codes"] = params.classification_codes

    if not clauses:
        return "TRUE", sql_params

    return " AND ".join(clauses), sql_params


def build_sort_clause(sort_by: str, sort_order: str) -> str:
    """Build an ORDER BY clause from sort parameters.

    Args:
        sort_by: One of 'relevance', 'posting_date', 'closing_date', 'value'.
        sort_order: One of 'asc', 'desc'.

    Returns:
        SQL ORDER BY clause string.
    """
    if sort_by == "relevance":
        return "ORDER BY rrf_score DESC"

    column_map = {
        "posting_date": "posting_date",
        "closing_date": "closing_date",
        "value": "value_max",
    }

    column = column_map.get(sort_by, "rrf_score")
    direction = sort_order.upper() if sort_order in ("asc", "desc") else "DESC"
    return f"ORDER BY {column} {direction} NULLS LAST"
