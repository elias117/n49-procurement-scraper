"""Hybrid keyword + semantic search with Reciprocal Rank Fusion (RRF).

Executes CTE-based queries combining tsvector keyword search and
pgvector cosine similarity, merged via RRF scoring.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import psycopg2.extras
from api import config
from api.models.request import SearchRequest
from api.search.query_builder import build_sort_clause


def _calculate_oversample(page_size: int) -> int:
    """Calculate oversample limit for sub-queries before RRF merge."""
    return min(page_size * config.RRF_OVERSAMPLE_FACTOR, 100)


def _calculate_offset(page: int, page_size: int) -> int:
    """Calculate SQL OFFSET from page number."""
    return (page - 1) * page_size


def _build_browse_sql(
    filter_clause: str, sort_by: str, sort_order: str
) -> str:
    """Build SQL for browse mode (no query text) -- filtered results only."""
    sort_clause = build_sort_clause(sort_by, sort_order)
    # For browse mode without relevance, fall back to posting_date desc
    if sort_by == "relevance":
        sort_clause = "ORDER BY posting_date DESC NULLS LAST"

    return f"""
WITH filtered AS (
    SELECT id, title, description, source_portal, closing_date,
           province, value_min, value_max, posting_date,
           classification_codes
    FROM listings
    WHERE {filter_clause}
),
total AS (
    SELECT COUNT(*) AS cnt FROM filtered
)
SELECT
    f.id, f.title, f.description, f.closing_date,
    f.province, f.value_min, f.value_max, f.posting_date,
    f.classification_codes,
    p.name AS portal_name,
    0.0 AS rrf_score,
    t.cnt AS total_count
FROM filtered f
JOIN portals p ON f.source_portal = p.id
CROSS JOIN total t
{sort_clause}
LIMIT %(page_size)s
OFFSET %(offset)s
"""


def _build_keyword_only_sql(filter_clause: str, sort_clause: str) -> str:
    """Build SQL for keyword-only search (no embedding available)."""
    return f"""
WITH filtered AS (
    SELECT id, title, description, source_portal, closing_date,
           province, value_min, value_max, posting_date,
           classification_codes, search_vector
    FROM listings
    WHERE {filter_clause}
),
keyword_search AS (
    SELECT id,
           ts_rank_cd(search_vector, websearch_to_tsquery('english', %(query)s)) AS rank_score
    FROM filtered
    WHERE search_vector @@ websearch_to_tsquery('english', %(query)s)
    ORDER BY rank_score DESC
    LIMIT %(oversample)s
),
total AS (
    SELECT COUNT(*) AS cnt FROM keyword_search
)
SELECT
    f.id, f.title, f.description, f.closing_date,
    f.province, f.value_min, f.value_max, f.posting_date,
    f.classification_codes,
    p.name AS portal_name,
    ks.rank_score AS rrf_score,
    t.cnt AS total_count
FROM keyword_search ks
JOIN filtered f ON ks.id = f.id
JOIN portals p ON f.source_portal = p.id
CROSS JOIN total t
{sort_clause}
LIMIT %(page_size)s
OFFSET %(offset)s
"""


def _build_hybrid_sql(filter_clause: str, sort_clause: str) -> str:
    """Build the full hybrid keyword + semantic RRF search SQL."""
    return f"""
WITH filtered AS (
    SELECT id, title, description, source_portal, closing_date,
           province, value_min, value_max, posting_date,
           classification_codes, embedding, search_vector
    FROM listings
    WHERE {filter_clause}
),
keyword_search AS (
    SELECT id,
           ROW_NUMBER() OVER (
               ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', %(query)s)) DESC
           ) AS rank_ix
    FROM filtered
    WHERE search_vector @@ websearch_to_tsquery('english', %(query)s)
    ORDER BY rank_ix
    LIMIT %(oversample)s
),
semantic_search AS (
    SELECT id,
           ROW_NUMBER() OVER (
               ORDER BY embedding <=> %(query_embedding)s::vector
           ) AS rank_ix
    FROM filtered
    WHERE embedding IS NOT NULL
    ORDER BY rank_ix
    LIMIT %(oversample)s
),
ranked AS (
    SELECT
        COALESCE(ks.id, ss.id) AS id,
        COALESCE(1.0 / (%(rrf_k)s + ks.rank_ix), 0.0) +
        COALESCE(1.0 / (%(rrf_k)s + ss.rank_ix), 0.0) AS rrf_score
    FROM keyword_search ks
    FULL OUTER JOIN semantic_search ss ON ks.id = ss.id
),
total AS (
    SELECT COUNT(*) AS cnt FROM ranked
)
SELECT
    f.id, f.title, f.description, f.closing_date,
    f.province, f.value_min, f.value_max, f.posting_date,
    f.classification_codes,
    p.name AS portal_name,
    r.rrf_score,
    t.cnt AS total_count
FROM ranked r
JOIN filtered f ON r.id = f.id
JOIN portals p ON f.source_portal = p.id
CROSS JOIN total t
{sort_clause}
LIMIT %(page_size)s
OFFSET %(offset)s
"""


def execute_hybrid_search(
    conn,
    params: SearchRequest,
    query_embedding: Optional[List[float]],
    filter_clause: str,
    filter_params: dict,
) -> Tuple[List[dict], int]:
    """Execute a hybrid search query and return results with total count.

    Args:
        conn: psycopg2 connection.
        params: SearchRequest with query, pagination, sort settings.
        query_embedding: Embedding vector for semantic search, or None to
            fall back to keyword-only.
        filter_clause: Pre-built SQL WHERE fragment from build_filter_clause.
        filter_params: Parameter dict from build_filter_clause.

    Returns:
        Tuple of (list_of_row_dicts, total_count).
    """
    oversample = _calculate_oversample(params.page_size)
    offset = _calculate_offset(params.page, params.page_size)
    sort_clause = build_sort_clause(params.sort_by, params.sort_order)

    # Merge filter params with search params
    sql_params = {**filter_params}
    sql_params["page_size"] = params.page_size
    sql_params["offset"] = offset

    has_query = bool(params.q and params.q.strip())

    if not has_query:
        # Browse mode -- no keyword or semantic search
        sql = _build_browse_sql(filter_clause, params.sort_by, params.sort_order)
    elif query_embedding is None:
        # Keyword-only fallback (embedding failed or exact mode)
        sql = _build_keyword_only_sql(filter_clause, sort_clause)
        sql_params["query"] = params.q
        sql_params["oversample"] = oversample
    else:
        # Full hybrid search with RRF
        sql = _build_hybrid_sql(filter_clause, sort_clause)
        sql_params["query"] = params.q
        sql_params["query_embedding"] = query_embedding
        sql_params["rrf_k"] = config.RRF_K
        sql_params["oversample"] = oversample

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(sql, sql_params)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    if not rows:
        return [], 0

    # Extract total_count from the first row (same across all rows via CROSS JOIN)
    total_count = rows[0].get("total_count", 0)

    # Convert RealDictRow to plain dicts
    results = [dict(row) for row in rows]

    return results, total_count
