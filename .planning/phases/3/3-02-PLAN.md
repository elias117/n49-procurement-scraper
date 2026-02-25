# Phase 3, Plan 02: Core Hybrid Search Engine

## Goal

Implement the complete search query pipeline: dynamic filter construction (all 6 dimensions), query embedding, keyword search (tsvector), semantic search (pgvector), RRF hybrid merge, sort options, and wire it all into the `/search` endpoint. After this plan, `GET /api/search?q=IT+consulting` returns ranked results from the database with all filters functional.

## Depends On

Plan 3-01 (API scaffold, models, DB connection, schema migration, test infrastructure).

## Requirements Addressed

SRCH-01 (keyword search), SRCH-02 (closing date filter), SRCH-03 (region filter), SRCH-04 (portal filter), SRCH-05 (posting date filter), SRCH-06 (classification code filter), SRCH-07 (semantic search), SRCH-08 (hybrid RRF), SRCH-09 (value range filter), SRCH-10 (sort options)

## Files Created/Modified

- `api/search/query_builder.py`
- `api/search/embeddings.py`
- `api/search/hybrid.py`
- `api/routers/search.py` (replace stub)
- `api/tests/test_query_builder.py` (replace scaffold)
- `api/tests/test_hybrid.py` (replace scaffold)
- `api/tests/test_search.py` (new -- endpoint integration tests)

## Tasks

### Wave 1: Filter Construction + Embedding Helper

#### Task 1.1: Implement dynamic SQL filter builder

**File:** `api/search/query_builder.py`
**Action:** Create
**Details:**

Create `build_filter_clause(params: SearchRequest) -> tuple[str, dict]` that returns a SQL WHERE fragment and a params dict for psycopg2 parameterized execution.

Filter logic per user decisions (CONTEXT.md locked):

1. **Open listings (default):** `(closing_date > NOW() - INTERVAL '48 hours' OR closing_date IS NULL)` -- 48h grace period, NULL = perpetually open. Skipped when `include_closed=True`.

2. **Regions (OR within):** `(province = ANY(%(regions)s) OR province IS NULL)` -- NULL province means National/unspecified, which is INCLUDED per user decision.

3. **Portals:** `source_portal = ANY(%(portals)s::uuid[])` -- simple IN.

4. **Closing date range:** `closing_date >= %(closing_date_from)s` and/or `closing_date <= %(closing_date_to)s`.

5. **Posting date range:** `posting_date >= %(posting_date_from)s` and/or `posting_date <= %(posting_date_to)s`.

6. **Contract value range:** When any value filter is active, first add `value_max IS NOT NULL` (exclude unknowns per user decision). Then `value_max >= %(value_min)s` and/or `value_min <= %(value_max)s` for range overlap logic.

7. **Classification codes:** `classification_codes IS NOT NULL AND EXISTS (SELECT 1 FROM jsonb_array_elements(classification_codes) elem WHERE elem->>'code' = ANY(%(classification_codes)s))` -- exclude NULL classification when filter active.

Also create `build_sort_clause(sort_by: str, sort_order: str) -> str`:
- `relevance` -> `ORDER BY rrf_score DESC` (ignore sort_order, relevance is always desc)
- `posting_date` -> `ORDER BY posting_date {sort_order} NULLS LAST`
- `closing_date` -> `ORDER BY closing_date {sort_order} NULLS LAST`
- `value` -> `ORDER BY value_max {sort_order} NULLS LAST`

All clauses joined with AND. Return `"TRUE"` if no filters active.

Use `%(param_name)s` format for psycopg2 named parameters throughout.

**Verify:** `python -m pytest api/tests/test_query_builder.py -x -q` passes.

#### Task 1.2: Write comprehensive filter builder tests

**File:** `api/tests/test_query_builder.py`
**Action:** Replace scaffold
**Details:**

Test cases (one test function each):

1. `test_no_filters_default_open()` -- No params except defaults. Should include the 48h closing_date clause and no other filters.

2. `test_include_closed_removes_date_guard()` -- `include_closed=True` should NOT include the closing_date > NOW() clause.

3. `test_region_filter_includes_null()` -- `regions=["Ontario"]` produces `(province = ANY(%(regions)s) OR province IS NULL)`. Verify NULL inclusion.

4. `test_portal_filter()` -- `portals=["uuid1", "uuid2"]` produces `source_portal = ANY(%(portals)s::uuid[])`.

5. `test_closing_date_range()` -- Both from and to set. Verify both clauses present.

6. `test_posting_date_range()` -- Both from and to set.

7. `test_value_filter_excludes_nulls()` -- `value_min=100000` should include `value_max IS NOT NULL` and `value_max >= %(value_min)s`.

8. `test_value_filter_range_overlap()` -- `value_min=100000, value_max=500000`. Verify range overlap: `value_max >= %(value_min)s AND value_min <= %(value_max)s`.

9. `test_classification_codes_filter()` -- `classification_codes=["541512"]`. Verify EXISTS subquery.

10. `test_combined_filters()` -- Regions + value range + include_closed. Verify AND joining and correct params dict keys.

11. `test_sort_relevance()` -- `sort_by="relevance"` returns `ORDER BY rrf_score DESC`.

12. `test_sort_posting_date_asc()` -- `sort_by="posting_date", sort_order="asc"` returns correct clause.

13. `test_sort_value_nulls_last()` -- `sort_by="value"` includes `NULLS LAST`.

Each test imports `build_filter_clause` / `build_sort_clause`, creates a `SearchRequest` with specific params, calls the function, and asserts on the returned SQL string and params dict.

**Verify:** `python -m pytest api/tests/test_query_builder.py -x -v` -- all 13 tests pass.

#### Task 1.3: Create query embedding helper

**File:** `api/search/embeddings.py`
**Action:** Create
**Details:**

```python
"""Query embedding generation using OpenAI API."""
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from api import config

# Module-level client (initialized once)
_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def embed_query(text: str) -> list[float]:
    """Embed a search query string for pgvector cosine similarity.

    Uses text-embedding-3-small (same model as scraper embeddings).
    Retries up to 3 times with exponential backoff on API errors.

    Args:
        text: The search query string to embed.

    Returns:
        List of 1536 floats (embedding vector).
    """
    client = _get_client()
    response = client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=[text],
    )
    return response.data[0].embedding
```

**Verify:** `python -c "from api.search.embeddings import embed_query; print('Import OK')"` succeeds.

### Wave 2: Hybrid Search SQL + Endpoint Wiring

#### Task 2.1: Implement hybrid search query execution

**File:** `api/search/hybrid.py`
**Action:** Create
**Details:**

Create `execute_hybrid_search(conn, params: SearchRequest, query_embedding: list[float] | None, filter_clause: str, filter_params: dict) -> tuple[list[dict], int]` that:

1. Receives pre-built `filter_clause` and `filter_params` from the caller (the router calls `build_filter_clause` once and passes the result to both `execute_hybrid_search` and `execute_facet_counts` in Plan 3-03, avoiding double-calling).
2. Builds the full CTE-based hybrid search SQL query:

```sql
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
OFFSET %(offset)s;
```

3. For total_count: run a separate lightweight count query using the same filtered CTE + keyword/semantic intersection logic, OR extract from a CTE. For simplicity at this scale, the `total` CTE above counts ranked results and is selected via `t.cnt` in the first row.

4. Return `(rows_as_dicts, total_count)`.

**Special cases:**
- If `params.q` is empty and mode is hybrid: skip keyword and semantic CTEs, just return filtered results sorted by the requested sort. This handles "browse all" with filters only.
- If `query_embedding` is None (embedding API failed or query is empty): fall back to keyword-only search (no semantic CTE, no RRF -- just ts_rank_cd ordering).
- Oversample: `min(params.page_size * config.RRF_OVERSAMPLE_FACTOR, 100)`
- Offset: `(params.page - 1) * params.page_size`

**Verify:** `python -c "from api.search.hybrid import execute_hybrid_search; print('Import OK')"` succeeds.

#### Task 2.2: Write hybrid search and RRF tests

**File:** `api/tests/test_hybrid.py`
**Action:** Replace scaffold
**Details:**

Test cases (mock DB, do not require running PostgreSQL):

1. `test_hybrid_search_builds_correct_sql()` -- Call with a query, default params, and pre-built filter_clause/filter_params. Mock `conn.cursor().execute()`. Assert the SQL string contains `keyword_search`, `semantic_search`, `rrf_score`, `FULL OUTER JOIN`, `total_count`. Assert params dict has `query`, `query_embedding`, `rrf_k`, `oversample`, `page_size`, `offset`.

2. `test_empty_query_skips_search_ctes()` -- Call with `q=""`. Assert the SQL does NOT contain `keyword_search` or `semantic_search` CTEs. Should fall back to filtered browse.

3. `test_none_embedding_falls_back_keyword_only()` -- Call with `query_embedding=None`. Assert SQL contains `keyword_search` but NOT `semantic_search`.

4. `test_oversample_calculation()` -- page_size=25, factor=4 -> oversample=100. page_size=50, factor=4 -> oversample=100 (capped).

5. `test_offset_calculation()` -- page=1 -> offset=0, page=3 -> offset=50 (page_size=25).

6. `test_rrf_k_from_config()` -- Assert the SQL params include `rrf_k` matching `config.RRF_K`.

**Verify:** `python -m pytest api/tests/test_hybrid.py -x -v` -- all 6 tests pass.

#### Task 2.3: Wire search endpoint with full parameter handling

**File:** `api/routers/search.py`
**Action:** Replace the stub from Plan 3-01
**Details:**

```python
"""Search endpoint -- hybrid keyword + semantic search with filters."""
import math
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime

from api.db import get_connection
from api.models.request import SearchRequest
from api.models.response import SearchResponse, ListingResult, FacetCounts
from api.search.hybrid import execute_hybrid_search
from api.search.query_builder import build_filter_clause
from api.search.embeddings import embed_query
from api import config

router = APIRouter(tags=["search"])

@router.get("/search", response_model=SearchResponse)
def search_listings(
    q: str = Query(default="", description="Search query"),
    mode: str = Query(default="hybrid", pattern="^(hybrid|exact)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=50),
    sort_by: str = Query(default="relevance", pattern="^(relevance|posting_date|closing_date|value)$"),
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
        q=q, mode=mode, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order,
        include_closed=include_closed, regions=regions,
        portals=portals, closing_date_from=closing_date_from,
        closing_date_to=closing_date_to,
        posting_date_from=posting_date_from,
        posting_date_to=posting_date_to,
        value_min=value_min, value_max=value_max,
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
            config.logger.warning("Embedding failed for query '%s', falling back to keyword-only", params.q)

    conn = get_connection()
    try:
        rows, total_count = execute_hybrid_search(
            conn, params, query_embedding, filter_clause, filter_params
        )
    finally:
        conn.close()

    results = [
        ListingResult(
            id=str(row["id"]),
            title=row["title"],
            source_portal_name=row["portal_name"],
            closing_date=row.get("closing_date"),
            province=row.get("province"),
            value_min=row.get("value_min"),
            value_max=row.get("value_max"),
            snippet=row.get("snippet", row.get("description", "")[:200] or ""),
            posting_date=row.get("posting_date"),
        )
        for row in rows
    ]

    total_pages = math.ceil(total_count / params.page_size) if total_count > 0 else 0

    return SearchResponse(
        results=results,
        total_count=total_count,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        facets=FacetCounts(),  # Facets added in Plan 3-03
    )
```

Note: The endpoint uses Query() params (not a request body) so it works with GET requests and is URL-shareable per Phase 4 requirements.

**Verify:** `python -c "from api.routers.search import search_listings; print('Endpoint OK')"` succeeds.

#### Task 2.4: Create search endpoint integration tests

**File:** `api/tests/test_search.py`
**Action:** Create
**Details:**

Integration tests that mock the database and OpenAI client:

1. `test_search_returns_200_with_results()` -- Mock `get_connection` to return mock conn, mock `embed_query` to return a vector. Mock cursor to return sample rows. `GET /search?q=IT+consulting` returns 200 with results.

2. `test_search_empty_query_returns_browse()` -- `GET /search` with no query returns 200 (browse mode).

3. `test_search_with_region_filter()` -- `GET /search?q=test&regions=Ontario` returns 200. Assert that the mock cursor received SQL with `province = ANY`.

4. `test_search_with_value_filter()` -- `GET /search?q=test&value_min=100000` returns 200.

5. `test_search_pagination()` -- `GET /search?q=test&page=2&page_size=10`. Assert response has `page=2`, `page_size=10`.

6. `test_search_exact_mode_skips_embedding()` -- `GET /search?q=tender123&mode=exact`. Assert `embed_query` was NOT called.

7. `test_search_embedding_failure_falls_back()` -- Mock `embed_query` to raise. Assert endpoint still returns 200 (keyword fallback).

**Verify:** `python -m pytest api/tests/test_search.py -x -v` -- all 7 tests pass.

## Plan Verification

Run all tests:
1. `python -m pytest api/tests/ -x -q` -- all tests pass (health: 2, query_builder: 13, hybrid: 6, search: 7, facets: 1 placeholder = 29 tests)
2. `python -c "from api.search.query_builder import build_filter_clause, build_sort_clause; print('Query builder OK')"` -- imports work
3. `python -c "from api.search.hybrid import execute_hybrid_search; print('Hybrid search OK')"` -- imports work
4. `python -c "from api.routers.search import search_listings; print('Search endpoint OK')"` -- imports work
