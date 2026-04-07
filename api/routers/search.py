"""Search endpoint -- hybrid keyword + semantic search with filters."""
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from api import config
from api.db import get_connection
from api.models.request import SearchRequest
from api.models.response import FacetCounts, ListingResult, SearchResponse
from api.search.embeddings import embed_query
from api.search.facets import execute_facet_counts
from api.search.hybrid import execute_exact_search, execute_hybrid_search
from api.search.query_builder import build_filter_clause

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_listings(
    q: str = Query(default="", description="Search query"),
    mode: str = Query(default="hybrid", pattern="^(hybrid|exact)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=50),
    sort_by: str = Query(
        default="relevance",
        pattern="^(relevance|posting_date|closing_date|value)$",
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    include_closed: bool = Query(default=False),
    regions: Optional[list[str]] = Query(default=None),
    portals: Optional[list[str]] = Query(default=None),
    closing_date_from: Optional[datetime] = Query(default=None),
    closing_date_to: Optional[datetime] = Query(default=None),
    posting_date_from: Optional[datetime] = Query(default=None),
    posting_date_to: Optional[datetime] = Query(default=None),
    value_min: Optional[float] = Query(default=None),
    value_max: Optional[float] = Query(default=None),
    classification_codes: Optional[list[str]] = Query(default=None),
):
    """Search procurement listings with hybrid keyword + semantic search."""
    params = SearchRequest(
        q=q,
        mode=mode,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_closed=include_closed,
        regions=regions,
        portals=portals,
        closing_date_from=closing_date_from,
        closing_date_to=closing_date_to,
        posting_date_from=posting_date_from,
        posting_date_to=posting_date_to,
        value_min=value_min,
        value_max=value_max,
        classification_codes=classification_codes,
    )

    # Build filter clause ONCE -- reused by both search and facets (Plan 3-03)
    filter_clause, filter_params = build_filter_clause(params)

    # Embed query for semantic search (skip if empty query or exact mode)
    query_embedding = None
    if params.q.strip() and params.mode == "hybrid":
        try:
            query_embedding = embed_query(params.q)
        except Exception:
            config.logger.warning(
                "Embedding failed for query '%s', falling back to keyword-only",
                params.q,
            )

    conn = get_connection()
    try:
        if params.mode == "exact" and params.q.strip():
            rows, total_count = execute_exact_search(
                conn, params, filter_clause, filter_params
            )
        else:
            rows, total_count = execute_hybrid_search(
                conn, params, query_embedding, filter_clause, filter_params
            )
        facets = execute_facet_counts(conn, filter_clause, filter_params)
    finally:
        conn.close()

    results = [
        ListingResult(
            id=str(row["id"]),
            title=row["title"],
            reference_number=row.get("reference_number"),
            source_listing_id=row.get("source_listing_id"),
            source_portal_name=row["portal_name"],
            closing_date=row.get("closing_date"),
            province=row.get("province"),
            value_min=row.get("value_min"),
            value_max=row.get("value_max"),
            snippet=row.get("snippet", ""),
            posting_date=row.get("posting_date"),
        )
        for row in rows
    ]

    total_pages = (
        math.ceil(total_count / params.page_size) if total_count > 0 else 0
    )

    return SearchResponse(
        results=results,
        total_count=total_count,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        facets=facets,
    )
