# Phase 3: Search Layer - Research

**Researched:** 2026-02-24
**Domain:** Hybrid search API (keyword + semantic), faceted filtering, pgvector + PostgreSQL FTS
**Confidence:** HIGH

## Summary

Phase 3 builds a FastAPI search API service that exposes hybrid keyword + semantic search over the ~900+ procurement listings already stored in PostgreSQL with pgvector. The core technical challenge is combining PostgreSQL's built-in full-text search (tsvector/GIN) with pgvector cosine similarity using Reciprocal Rank Fusion (RRF), then layering six filter dimensions, facet counts, pagination, and keyword-highlighted snippets on top.

The existing codebase uses psycopg2 (sync driver) with raw SQL in the scraper. For the search API, the research recommends FastAPI with psycopg2 (matching the existing stack) rather than introducing asyncpg/SQLAlchemy -- at <5K listings and <20 users, async provides no measurable benefit and adds complexity. The hybrid search query runs two sub-queries (FTS rank + vector cosine distance), unions them with RANK() window functions, and merges via RRF scoring at the SQL level. Filters are applied as WHERE clauses before ranking. Facet counts use a parallel CTE against the filtered (but unpaginated) result set.

**Primary recommendation:** Build a new `api/` service directory with FastAPI, reuse psycopg2 patterns from `scraper/db.py`, implement hybrid search as a single PostgreSQL CTE-based query with RRF, and deploy as a new Docker Compose service proxied through nginx at `/api/`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Search box is hybrid only** -- no auto-extraction of filters from natural language. The search box runs combined keyword + semantic search (RRF). Structured filters (region, date range, value range, category, portal, sort) are separate dedicated controls in the dashboard.
- **Two search modes:** hybrid (default) and exact match (toggle). Exact match is for tender numbers or specific titles. No other modes.
- **RRF weighting handles short vs long queries implicitly** -- short queries naturally get stronger keyword hits, longer queries get better semantic matches. Tune `k` parameters after real data exists; do not over-engineer upfront.
- **List result fields:** title, source portal, closing date, region, contract value (if available), 1-2 line description snippet with keyword highlights (bold matched terms).
- **Relevance score is internal** -- used for sorting, never surfaced to the user as a raw number.
- **Keyword highlights required** -- return highlighted snippets showing why a result matched. Standard search UX for trust and scannability.
- **Facet counts required** -- return counts per filter value (e.g., "Ontario (42), Federal (31)") alongside results. At 1-5K listings, overhead is negligible (GROUP BY counts).
- **Offset-based pagination** -- LIMIT/OFFSET, page size 25 or 50. No cursor-based pagination needed at this data volume. Users can jump to any page.
- **"Open" definition:** closing_date > now() - 48 hours. 48-hour grace period accounts for slow government portal updates.
- **No closing date = perpetually open** -- always included in default results. Standing offers and supply arrangements are high-value and must not be hidden.
- **Expired listings are searchable** -- "Include closed" toggle, off by default. Past listings have competitive intelligence value.
- **AND across dimensions, OR within dimension** -- "Ontario OR Quebec" + "closing next 30 days" + "$100K-$500K" applies all three constraints with AND.
- **Missing contract value + value filter active = excluded.** Deliberate filtering should not be diluted by null-value listings.
- **Missing category + category filter active = excluded.** Same logic as value.
- **National/unspecified region + province filter active = included.** National federal tenders apply everywhere.
- Add `original_closing_date` field to listings table for amendment tracking.

### Claude's Discretion
- RRF k parameter value (start with k=60, standard default)
- Internal oversampling factor for hybrid search (fetch 2x-4x match_count from each sub-query before RRF merge)
- API framework details (FastAPI routing structure, response models)
- Test query set composition for validation

### Deferred Ideas (OUT OF SCOPE)
None captured during discussion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRCH-01 | Full-text keyword search across title and description | PostgreSQL tsvector GIN index (already exists), `websearch_to_tsquery` for user input, `ts_rank_cd` for ranking |
| SRCH-02 | Filter by closing date range (default: open/future) | WHERE clause with closing_date range + 48-hour grace period + NULL handling |
| SRCH-03 | Filter by region/province | WHERE clause with OR-within-dimension + "National" inclusion logic |
| SRCH-04 | Filter by source portal | WHERE clause with portal UUID IN list |
| SRCH-05 | Filter by posting date range | WHERE clause with posting_date range |
| SRCH-06 | Filter by category/commodity code (NAICS/UNSPSC/GSIN) | JSONB containment query on classification_codes array |
| SRCH-07 | Semantic search via pgvector cosine similarity | Embed query with text-embedding-3-small, use `<=>` cosine distance operator with HNSW index |
| SRCH-08 | Hybrid search via Reciprocal Rank Fusion | Two sub-queries (FTS + vector), RANK() window functions, RRF score aggregation |
| SRCH-09 | Filter by estimated contract value range | WHERE clause on value_min/value_max with NULL exclusion when filter active |
| SRCH-10 | Sort by posting date, closing date, relevance, contract value | ORDER BY clause switching based on sort parameter; relevance = RRF score |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | HTTP API framework | Async-capable, Pydantic-native, auto-generates OpenAPI docs. Already prescribed in project STACK.md. Lightweight enough for a search-only API. |
| psycopg2-binary | 2.9.10 | PostgreSQL driver | Already used by scraper. Proven in this codebase. No need to introduce asyncpg for <20 concurrent users. |
| pydantic | 2.x | Request/response validation | Already a dependency. FastAPI requires it. Models shared with scraper. |
| openai | 1.x | Query embedding generation | Already a dependency. Same client/key used by scraper for listing embeddings. |
| uvicorn | 0.30+ | ASGI server | Standard FastAPI production server. Runs behind nginx. |
| httpx | 0.27+ | HTTP client (for tests) | Already a dependency. FastAPI TestClient uses it. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tiktoken | 0.5+ | Token counting for query text | Already a dependency. Validate query length before embedding API call. |
| tenacity | 8.x | Retry for OpenAI API calls | Already a dependency. Wrap embedding call with exponential backoff. |
| pytest | 8.x | Testing | Already configured. Extend testpaths in pytest.ini. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg2 (sync) | asyncpg + SQLAlchemy async | Better for high concurrency but adds complexity; psycopg2 is already proven in codebase, <20 users makes async unnecessary |
| FastAPI | Flask | Flask lacks auto OpenAPI docs, native Pydantic validation, and async support. FastAPI is the modern standard. |
| Raw SQL | SQLAlchemy ORM | ORM adds abstraction layer; raw SQL is clearer for complex hybrid search queries with CTEs and window functions |
| psycopg2 connection per request | Connection pool (psycopg2.pool) | At <20 users, simple connections are fine; add pool if latency becomes an issue |

**Installation (new api/requirements.txt):**
```bash
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
psycopg2-binary==2.9.10
pydantic>=2.0,<3.0
openai>=1.0,<2.0
tiktoken>=0.5,<1.0
tenacity>=8.0,<9.0
httpx>=0.27,<1.0
pytest>=8.0,<9.0
```

## Architecture Patterns

### Recommended Project Structure

```
api/
  Dockerfile
  requirements.txt
  main.py                  # FastAPI app creation, lifespan, CORS
  config.py                # Env vars: DATABASE_URL, OPENAI_API_KEY
  routers/
    search.py              # GET /api/search — hybrid search endpoint
    health.py              # GET /api/health — health check
  db.py                    # Connection helper (reuse pattern from scraper/db.py)
  search/
    __init__.py
    query_builder.py       # Dynamic SQL construction with filters
    hybrid.py              # RRF hybrid search logic
    embeddings.py          # Query embedding (thin wrapper around OpenAI)
    highlights.py          # ts_headline snippet generation
    facets.py              # Facet count queries
  models/
    __init__.py
    request.py             # SearchRequest Pydantic model
    response.py            # SearchResponse, ListingResult, FacetCounts models
  tests/
    __init__.py
    conftest.py            # Fixtures: mock DB, sample data
    test_search.py         # Integration tests for search endpoint
    test_query_builder.py  # Unit tests for SQL construction
    test_hybrid.py         # Unit tests for RRF logic
    test_facets.py         # Unit tests for facet counts
```

### Pattern 1: Hybrid Search with RRF (Single SQL Query)

**What:** Run keyword search and semantic search as sub-queries within a single SQL statement, combine via RRF scoring using window functions.

**When to use:** Every hybrid search request (the default mode).

**Example (verified pattern from Jonathan Katz's blog + Supabase docs):**
```sql
WITH filtered AS (
    -- Apply all WHERE filters first to reduce the candidate set
    SELECT id, title, description, source_portal, closing_date,
           province, value_min, value_max, posting_date,
           classification_codes, embedding
    FROM listings
    WHERE
        -- Open listings filter (default: on)
        (closing_date > NOW() - INTERVAL '48 hours' OR closing_date IS NULL)
        -- Additional dynamic filters appended here
),
keyword_search AS (
    SELECT id,
           ROW_NUMBER() OVER (
               ORDER BY ts_rank_cd(
                   to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')),
                   websearch_to_tsquery('english', %(query)s)
               ) DESC
           ) AS rank_ix
    FROM filtered
    WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
          @@ websearch_to_tsquery('english', %(query)s)
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
)
SELECT
    f.id, f.title, f.description, f.source_portal, f.closing_date,
    f.province, f.value_min, f.value_max, f.posting_date,
    f.classification_codes,
    ts_headline('english',
        coalesce(f.description, f.title),
        websearch_to_tsquery('english', %(query)s),
        'MaxWords=35, MinWords=15, StartSel=<mark>, StopSel=</mark>, MaxFragments=2, FragmentDelimiter= ... '
    ) AS snippet,
    COALESCE(1.0 / (%(rrf_k)s + ks.rank_ix), 0.0) +
    COALESCE(1.0 / (%(rrf_k)s + ss.rank_ix), 0.0) AS rrf_score
FROM keyword_search ks
FULL OUTER JOIN semantic_search ss ON ks.id = ss.id
JOIN filtered f ON COALESCE(ks.id, ss.id) = f.id
ORDER BY rrf_score DESC
LIMIT %(page_size)s
OFFSET %(offset)s;
```

### Pattern 2: Exact Match Mode

**What:** When exact match toggle is on, use `phraseto_tsquery` or direct ILIKE for tender number/title matching. No semantic search.

**When to use:** User toggles exact match for tender numbers like "EN578-200001/A".

**Example:**
```sql
SELECT id, title, description, source_portal, closing_date,
       province, value_min, value_max, posting_date,
       ts_headline('english', coalesce(description, title),
           phraseto_tsquery('english', %(query)s),
           'MaxWords=35, MinWords=15, StartSel=<mark>, StopSel=</mark>')
       AS snippet
FROM listings
WHERE
    title ILIKE '%%' || %(query)s || '%%'
    OR description ILIKE '%%' || %(query)s || '%%'
    OR source_listing_id ILIKE '%%' || %(query)s || '%%'
ORDER BY
    CASE WHEN title ILIKE '%%' || %(query)s || '%%' THEN 0 ELSE 1 END,
    closing_date DESC NULLS LAST
LIMIT %(page_size)s OFFSET %(offset)s;
```

### Pattern 3: Dynamic Filter Construction

**What:** Build WHERE clauses dynamically based on which filters are active, using parameterized queries for safety.

**When to use:** Every search request (filters are optional).

**Example:**
```python
def build_filter_clause(params: SearchRequest) -> tuple[str, dict]:
    """Build dynamic WHERE clause from search parameters.

    Returns (sql_fragment, params_dict) for safe parameterized execution.
    """
    clauses = []
    values = {}

    # Default: open listings only (unless include_closed is True)
    if not params.include_closed:
        clauses.append(
            "(closing_date > NOW() - INTERVAL '48 hours' OR closing_date IS NULL)"
        )

    # Region filter: OR within dimension, include "National"
    if params.regions:
        clauses.append(
            "(province = ANY(%(regions)s) OR province IS NULL)"
        )
        values["regions"] = params.regions

    # Source portal filter
    if params.portals:
        clauses.append("source_portal = ANY(%(portals)s::uuid[])")
        values["portals"] = params.portals

    # Closing date range
    if params.closing_date_from:
        clauses.append("closing_date >= %(closing_date_from)s")
        values["closing_date_from"] = params.closing_date_from
    if params.closing_date_to:
        clauses.append("closing_date <= %(closing_date_to)s")
        values["closing_date_to"] = params.closing_date_to

    # Posting date range
    if params.posting_date_from:
        clauses.append("posting_date >= %(posting_date_from)s")
        values["posting_date_from"] = params.posting_date_from
    if params.posting_date_to:
        clauses.append("posting_date <= %(posting_date_to)s")
        values["posting_date_to"] = params.posting_date_to

    # Contract value range (exclude NULLs when filter active)
    if params.value_min is not None or params.value_max is not None:
        clauses.append("value_max IS NOT NULL")  # Exclude unknowns
        if params.value_min is not None:
            clauses.append("value_max >= %(value_min)s")
            values["value_min"] = params.value_min
        if params.value_max is not None:
            clauses.append("value_min <= %(value_max)s")
            values["value_max"] = params.value_max

    # Classification codes (JSONB containment)
    if params.classification_codes:
        clauses.append(
            "classification_codes IS NOT NULL AND "
            "EXISTS (SELECT 1 FROM jsonb_array_elements(classification_codes) elem "
            "WHERE elem->>'code' = ANY(%(classification_codes)s))"
        )
        values["classification_codes"] = params.classification_codes

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return where_sql, values
```

### Pattern 4: Facet Counts via Parallel CTE

**What:** Compute facet counts from the filtered result set (before pagination) in a single query alongside the search results.

**When to use:** Every search response includes facet counts.

**Example:**
```sql
WITH filtered AS (
    SELECT id, province, source_portal, classification_codes,
           value_min, value_max
    FROM listings
    WHERE {filter_clauses}
),
province_facets AS (
    SELECT COALESCE(province, 'National') AS facet_value,
           COUNT(*) AS count
    FROM filtered
    GROUP BY COALESCE(province, 'National')
    ORDER BY count DESC
),
portal_facets AS (
    SELECT p.name AS facet_value, COUNT(*) AS count
    FROM filtered f
    JOIN portals p ON f.source_portal = p.id
    GROUP BY p.name
    ORDER BY count DESC
)
SELECT 'province' AS facet_type, facet_value, count FROM province_facets
UNION ALL
SELECT 'portal' AS facet_type, facet_value, count FROM portal_facets;
```

### Anti-Patterns to Avoid

- **Embedding queries at the application level in Python RRF:** Do NOT fetch all results from both searches into Python, merge in-memory, then paginate. At 1-5K listings this "works" but it defeats PostgreSQL's query optimizer and prevents LIMIT pushdown. Keep RRF in SQL.
- **Using to_tsquery with raw user input:** Use `websearch_to_tsquery` instead -- it never raises syntax errors on malformed input and supports natural operators (OR, -, quoted phrases).
- **Recomputing tsvector in every query:** The existing GIN index is on `to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))`. The search query MUST use the exact same expression to hit the index. Alternatively, add a stored generated column (see migration recommendations).
- **Forgetting NULL handling in region filter:** The CONTEXT.md explicitly states "National/unspecified region + province filter active = included." This means `province IS NULL` rows must be included when any province filter is active.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query embedding | Custom embedding pipeline | `openai.embeddings.create()` | Already proven in scraper/pipeline/embeddings.py. Single API call, ~100ms latency. |
| Keyword highlighting | Custom regex-based highlighting | `ts_headline()` with StartSel/StopSel | PostgreSQL built-in, handles stemming and stop words correctly. HTML sanitization needed on output. |
| RRF score calculation | Custom Python merge logic | SQL FULL OUTER JOIN + COALESCE formula | Keep in SQL for query optimizer benefits and pagination pushdown. |
| API input validation | Manual request parsing | Pydantic models + FastAPI Query params | FastAPI auto-validates, auto-documents, generates OpenAPI spec. |
| OpenAPI documentation | Swagger YAML files | FastAPI auto-generation | FastAPI generates /docs and /openapi.json automatically from type hints. |
| Connection management | Custom pool | `psycopg2.connect()` per request | At <20 concurrent users, connection-per-request is fine. Add `psycopg2.pool.SimpleConnectionPool` only if latency degrades. |

**Key insight:** PostgreSQL already has every building block needed for this search layer (tsvector, pgvector, ts_headline, window functions, CTEs). The API layer is thin glue -- query construction, embedding, and response shaping. Resist the urge to pull logic out of SQL into Python.

## Common Pitfalls

### Pitfall 1: tsvector Expression Mismatch
**What goes wrong:** The search query uses a slightly different tsvector expression than the one the GIN index was built on, causing a sequential scan instead of index scan.
**Why it happens:** The existing index is on `to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))`. If the search query uses `to_tsvector('english', title || ' ' || description)` (without COALESCE), PostgreSQL cannot use the index.
**How to avoid:** Copy the exact expression from `001_initial_schema.sql` line 56. Better yet, add a stored generated tsvector column in a migration and reindex.
**Warning signs:** EXPLAIN ANALYZE shows `Seq Scan` instead of `Bitmap Index Scan` on the FTS query.

### Pitfall 2: ts_headline Performance on Large Text
**What goes wrong:** `ts_headline` re-parses the original document text (not the tsvector). On listings with very long descriptions, this is slow.
**Why it happens:** ts_headline cannot use the tsvector index -- it needs the raw text to generate snippets.
**How to avoid:** Apply ts_headline only to the paginated result set (after LIMIT/OFFSET), not to the full candidate set. The CTE structure in Pattern 1 handles this correctly because ts_headline is in the final SELECT that operates on already-ranked-and-limited rows.
**Warning signs:** Search latency >500ms when it should be <100ms at this scale.

### Pitfall 3: Embedding NULL Rows in Semantic Search
**What goes wrong:** Rows with `embedding IS NULL` cause errors or get excluded silently from semantic search, making them unfindable via natural language.
**Why it happens:** Some listings may not have embeddings (e.g., embedding API failure during scrape).
**How to avoid:** Add `WHERE embedding IS NOT NULL` to the semantic search CTE. These rows can still appear via keyword search. Log a warning for NULL embedding counts.
**Warning signs:** Listings that match keywords but never appear in semantic results.

### Pitfall 4: JSONB Classification Code Filtering
**What goes wrong:** Querying `classification_codes @> '[{"code": "541512"}]'::jsonb` does not work as expected because the JSONB structure includes `system` and `description` keys too.
**Why it happens:** JSONB `@>` containment requires the query to be a subset of the stored value, including all keys in the object.
**How to avoid:** Use `jsonb_array_elements` with a subquery: `EXISTS (SELECT 1 FROM jsonb_array_elements(classification_codes) elem WHERE elem->>'code' = ANY(%(codes)s))`.
**Warning signs:** Category filter returns no results even when codes exist in the data.

### Pitfall 5: OFFSET Performance at Scale
**What goes wrong:** OFFSET 10000 with LIMIT 25 forces PostgreSQL to compute and discard 10,000 rows.
**Why it happens:** OFFSET-based pagination is O(offset + limit).
**How to avoid:** At 1-5K total listings, this is a non-issue. Maximum realistic offset is ~200 (5000/25 = 200 pages). If data grows to 50K+, switch to keyset pagination. For now, LIMIT/OFFSET is the correct choice per CONTEXT.md.
**Warning signs:** Page load time increases linearly with page number.

### Pitfall 6: XSS via ts_headline Output
**What goes wrong:** `ts_headline` output can contain unsanitized HTML from the original document text.
**Why it happens:** PostgreSQL docs explicitly warn: "The output is not guaranteed to be safe." The StartSel/StopSel tags are inserted, but existing HTML in the document is not fully stripped.
**How to avoid:** Sanitize the description text before passing to ts_headline (strip HTML tags), OR sanitize the output. The API should return safe HTML snippets.
**Warning signs:** Rendered search results show broken HTML or script injection.

### Pitfall 7: OpenAI Embedding Latency on Search
**What goes wrong:** Each search request requires an OpenAI API call to embed the query text (~100-300ms). This adds to perceived search latency.
**Why it happens:** The query must be embedded in the same vector space as stored listings.
**How to avoid:** Accept this latency (100-300ms is acceptable for search). Cache embeddings for repeated identical queries using a simple LRU dict (optional optimization). Do NOT pre-embed queries -- the query is user-generated and unpredictable.
**Warning signs:** P95 search latency >1s. Check if it is the embedding API call or the SQL query.

## Code Examples

### FastAPI Search Endpoint
```python
# Source: FastAPI docs + project conventions
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SearchRequest(BaseModel):
    q: str = Field(default="", description="Search query text")
    mode: str = Field(default="hybrid", pattern="^(hybrid|exact)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=50)
    sort_by: str = Field(default="relevance", pattern="^(relevance|posting_date|closing_date|value)$")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    include_closed: bool = Field(default=False)
    regions: Optional[list[str]] = None
    portals: Optional[list[str]] = None
    closing_date_from: Optional[datetime] = None
    closing_date_to: Optional[datetime] = None
    posting_date_from: Optional[datetime] = None
    posting_date_to: Optional[datetime] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    classification_codes: Optional[list[str]] = None

class ListingResult(BaseModel):
    id: str
    title: str
    source_portal_name: str
    closing_date: Optional[datetime]
    province: Optional[str]
    value_min: Optional[float]
    value_max: Optional[float]
    snippet: str  # HTML-highlighted excerpt
    posting_date: Optional[datetime]

class FacetValue(BaseModel):
    value: str
    count: int

class FacetCounts(BaseModel):
    provinces: list[FacetValue]
    portals: list[FacetValue]

class SearchResponse(BaseModel):
    results: list[ListingResult]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    facets: FacetCounts
```

### Query Embedding Helper
```python
# Source: reuses pattern from scraper/pipeline/embeddings.py
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

EMBEDDING_MODEL = "text-embedding-3-small"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def embed_query(client: OpenAI, text: str) -> list[float]:
    """Embed a search query string for pgvector cosine similarity."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    return response.data[0].embedding
```

### Docker Compose Addition
```yaml
# New service added to docker-compose.yml
  api:
    build: ./api
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "8000"
    networks:
      - internal
```

### Nginx Route Addition
```nginx
# Add to nginx/nginx.conf inside server block
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```

### Schema Migration: Stored tsvector Column + original_closing_date
```sql
-- 004_search_layer.sql

-- Add stored generated tsvector column for index-aligned queries
ALTER TABLE listings ADD COLUMN IF NOT EXISTS
    search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED;

-- Create GIN index on the stored column (can coexist with existing expression index)
CREATE INDEX IF NOT EXISTS listings_search_vector_idx
    ON listings USING GIN (search_vector);

-- Add original_closing_date per CONTEXT.md decision
ALTER TABLE listings ADD COLUMN IF NOT EXISTS original_closing_date TIMESTAMPTZ;
```

Using the stored `search_vector` column, the FTS query simplifies to:
```sql
WHERE search_vector @@ websearch_to_tsquery('english', %(query)s)
ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', %(query)s)) DESC
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `plainto_tsquery` for user input | `websearch_to_tsquery` | PostgreSQL 11 (2018) | Safer user input handling, supports OR/-/quotes natively |
| IVFFlat for vector index | HNSW (already in use) | pgvector 0.5.0 (2023) | Better recall/speed tradeoff; no need to retrain on data changes |
| Application-level RRF merge | SQL-level RRF with CTEs | 2024-2025 community patterns | PostgreSQL optimizer handles pagination correctly; fewer round-trips |
| ts_rank for FTS ranking | ts_rank_cd (cover density) | Long-standing | Better relevance for document-style text; weights proximity of matched terms |
| Expression-based tsvector in queries | Stored generated tsvector column | PostgreSQL 12 (2019) | Guarantees index alignment, simpler query syntax, slight storage cost |

**Deprecated/outdated:**
- `to_tsquery` with raw user input: Never use -- syntax errors on invalid input. Use `websearch_to_tsquery`.
- IVFFlat index type: Still works but HNSW is strictly better for this use case (no retraining needed).

## Open Questions

1. **RRF k parameter optimal value**
   - What we know: k=60 is the original paper default. k=50 is used by Supabase. Both are valid.
   - What is unclear: Optimal k depends on the data distribution and query patterns.
   - Recommendation: Start with k=60, make it configurable via environment variable. Tune after 20 real queries are validated.

2. **Oversampling factor for sub-queries**
   - What we know: Each sub-query (keyword + semantic) should return more results than the final page size to ensure good RRF merge quality.
   - What is unclear: Optimal oversampling ratio.
   - Recommendation: Use `min(page_size * 4, 100)` as the LIMIT for each sub-query. At 25 results/page, this means 100 candidates from each method, merged to 25.

3. **French language listings**
   - What we know: Some portals are French-language. The tsvector config is `'english'`.
   - What is unclear: Whether French listings are currently in the DB, and whether we need a French tsvector config.
   - Recommendation: Keep `'english'` for now. Add `'french'` config and language-aware search in a future iteration if French content volume warrants it.

4. **Facet count consistency with paginated results**
   - What we know: Facet counts should reflect the filtered total, not just the current page.
   - What is unclear: Whether to run facets as a separate query or within the same transaction.
   - Recommendation: Run facets in the same query (CTE-based) or same transaction to ensure consistency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `/Users/clawbot/dev/pytest.ini` (exists, needs testpaths update) |
| Quick run command | `pytest api/tests/ -x -q` |
| Full suite command | `pytest api/tests/ -v` |
| Estimated runtime | ~5-10 seconds (unit tests mock DB; integration tests need DB) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-01 | Keyword search returns relevant results | unit + integration | `pytest api/tests/test_search.py::test_keyword_search -x` | No -- Wave 0 gap |
| SRCH-02 | Closing date filter with 48h grace | unit | `pytest api/tests/test_query_builder.py::test_closing_date_filter -x` | No -- Wave 0 gap |
| SRCH-03 | Region filter with National inclusion | unit | `pytest api/tests/test_query_builder.py::test_region_filter -x` | No -- Wave 0 gap |
| SRCH-04 | Source portal filter | unit | `pytest api/tests/test_query_builder.py::test_portal_filter -x` | No -- Wave 0 gap |
| SRCH-05 | Posting date range filter | unit | `pytest api/tests/test_query_builder.py::test_posting_date_filter -x` | No -- Wave 0 gap |
| SRCH-06 | Classification code JSONB filter | unit | `pytest api/tests/test_query_builder.py::test_classification_filter -x` | No -- Wave 0 gap |
| SRCH-07 | Semantic search returns relevant results | integration | `pytest api/tests/test_search.py::test_semantic_search -x` | No -- Wave 0 gap |
| SRCH-08 | Hybrid RRF merges both result sets | unit + integration | `pytest api/tests/test_hybrid.py::test_rrf_merge -x` | No -- Wave 0 gap |
| SRCH-09 | Value range filter excludes NULLs | unit | `pytest api/tests/test_query_builder.py::test_value_filter -x` | No -- Wave 0 gap |
| SRCH-10 | Sort by relevance/date/value | unit | `pytest api/tests/test_query_builder.py::test_sort_options -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task, run: `pytest api/tests/ -x -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~5 seconds (unit tests only)

### Wave 0 Gaps (must be created before implementation)
- [ ] `api/tests/__init__.py` -- package init
- [ ] `api/tests/conftest.py` -- shared fixtures (mock DB connection, sample listings, mock OpenAI client)
- [ ] `api/tests/test_search.py` -- endpoint-level tests for search API
- [ ] `api/tests/test_query_builder.py` -- unit tests for dynamic SQL construction
- [ ] `api/tests/test_hybrid.py` -- unit tests for RRF scoring logic
- [ ] `api/tests/test_facets.py` -- unit tests for facet count queries
- [ ] `pytest.ini` update -- add `api/tests` to testpaths
- [ ] Framework install: `pip install fastapi uvicorn httpx` -- FastAPI not yet installed

## Sources

### Primary (HIGH confidence)
- [PostgreSQL 18 docs: Controlling Text Search](https://www.postgresql.org/docs/current/textsearch-controls.html) -- ts_headline, websearch_to_tsquery, ts_rank_cd options and behavior
- [pgvector GitHub](https://github.com/pgvector/pgvector) -- HNSW index parameters, cosine distance operator, ef_search tuning
- [Jonathan Katz: Hybrid Search with PostgreSQL and pgvector](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/) -- Complete SQL pattern for RRF with CTEs and window functions
- [Supabase: Hybrid Search docs](https://supabase.com/docs/guides/ai/hybrid-search) -- PostgreSQL function implementing RRF with full_text_weight and semantic_weight
- [FastAPI Official Documentation](https://fastapi.tiangolo.com/) -- Framework patterns, Pydantic integration, deployment
- [psycopg2 docs: sql module](https://www.psycopg.org/docs/sql.html) -- Safe dynamic SQL construction

### Secondary (MEDIUM confidence)
- [DEV Community: Building Hybrid Search with RRF](https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk) -- Python RRF implementation pattern, ~62% to ~84% precision improvement verified
- [ParadeDB: Hybrid Search Missing Manual](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) -- RRF formula explanation, k parameter guidance
- [CyberTec: Faceting Large Result Sets](https://www.cybertec-postgresql.com/en/faceting-large-result-sets/) -- PostgreSQL facet count patterns at scale
- [Google Cloud: pgvector index tuning](https://cloud.google.com/blog/products/databases/faster-similarity-search-performance-with-pgvector-indexes) -- ef_search parameter guidance

### Tertiary (LOW confidence)
- [FastAPI GitHub Discussion #13732](https://github.com/fastapi/fastapi/discussions/13732) -- psycopg2 vs asyncpg benchmarks (community benchmarks, not official)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- FastAPI + psycopg2 + pgvector are well-documented, already partially in use
- Architecture: HIGH -- CTE-based hybrid search with RRF is a proven pattern with multiple authoritative sources
- Pitfalls: HIGH -- All pitfalls identified from official PostgreSQL documentation and real implementation experience
- Filter logic: HIGH -- CONTEXT.md provides explicit rules for every edge case (NULL handling, National inclusion, AND/OR semantics)
- Facet implementation: MEDIUM -- Pattern is straightforward but not verified against this specific schema
- RRF k parameter: MEDIUM -- Default values well-documented but optimal tuning requires real query validation

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain, 30-day window)
