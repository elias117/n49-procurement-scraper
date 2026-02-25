# Phase 3, Plan 03: Search UX Features -- Facets, Highlights, Exact Match, Pagination

## Goal

Add the search UX features that complete the API contract: facet counts (province + portal breakdowns alongside results), keyword-highlighted snippets via `ts_headline` with XSS sanitization, exact match mode (ILIKE + phraseto_tsquery for tender numbers), and correct total_count for pagination. After this plan, the search endpoint returns production-ready responses with facets, highlighted snippets, and both search modes working.

## Depends On

Plan 3-02 (hybrid search engine, filter builder, search endpoint wiring).

## Requirements Addressed

SRCH-01 (keyword highlights), SRCH-08 (facet counts enrich hybrid results), SRCH-10 (pagination total_count)

## Files Created/Modified

- `api/search/facets.py`
- `api/search/highlights.py`
- `api/search/hybrid.py` (edit -- add ts_headline to result query, integrate facets)
- `api/routers/search.py` (edit -- wire facets into response)
- `api/tests/test_facets.py` (replace scaffold)
- `api/tests/test_highlights.py` (new)
- `api/tests/test_exact_match.py` (new)

## Tasks

### Wave 1: Facets + Highlights Modules

#### Task 1.1: Implement facet count queries

**File:** `api/search/facets.py`
**Action:** Create
**Details:**

Create `execute_facet_counts(conn, filter_clause: str, filter_params: dict) -> FacetCounts` that runs a single query returning province and portal facet counts from the filtered result set (before pagination).

SQL pattern:
```sql
WITH filtered AS (
    SELECT id, province, source_portal
    FROM listings
    WHERE {filter_clause}
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

Parse the rows into a `FacetCounts` object with `provinces` and `portals` lists of `FacetValue`.

The filter_clause and filter_params come from the same `build_filter_clause()` call that the search query uses, ensuring facet counts reflect the same filters (minus pagination).

**Verify:** `python -c "from api.search.facets import execute_facet_counts; print('Facets OK')"` succeeds.

#### Task 1.2: Write facet count tests

**File:** `api/tests/test_facets.py`
**Action:** Replace scaffold
**Details:**

1. `test_facets_returns_province_counts()` -- Mock cursor to return province facet rows. Assert `FacetCounts.provinces` has correct values and counts, sorted desc.

2. `test_facets_returns_portal_counts()` -- Mock cursor to return portal facet rows. Assert `FacetCounts.portals` has correct values.

3. `test_facets_null_province_becomes_national()` -- Mock data includes NULL province. Assert it appears as "National" in the output.

4. `test_facets_empty_result_set()` -- Mock cursor returns no rows. Assert `FacetCounts` with empty lists.

5. `test_facets_uses_same_filter_clause()` -- Pass a filter clause string and params dict. Assert the SQL executed contains the filter clause.

**Verify:** `python -m pytest api/tests/test_facets.py -x -v` -- all 5 tests pass.

#### Task 1.3: Implement keyword highlight sanitization

**File:** `api/search/highlights.py`
**Action:** Create
**Details:**

Create `sanitize_snippet(raw_snippet: str) -> str` that:

1. Takes the raw `ts_headline` output (which may contain arbitrary HTML from the source document).
2. Strips all HTML tags EXCEPT `<mark>` and `</mark>` (our StartSel/StopSel tags).
3. Uses the `bleach` library: `bleach.clean(raw_snippet, tags=["mark"], strip=True)`.
4. Returns the sanitized string.

This addresses the XSS risk documented in the research (Pitfall 6: PostgreSQL docs explicitly warn ts_headline output is not safe).

Also create the `TS_HEADLINE_OPTIONS` constant string used in SQL:
```python
TS_HEADLINE_OPTIONS = (
    "MaxWords=35, MinWords=15, "
    "StartSel=<mark>, StopSel=</mark>, "
    "MaxFragments=2, FragmentDelimiter= ... "
)
```

**Verify:** `python -m pytest api/tests/test_highlights.py -x -v` passes.

#### Task 1.4: Write highlight sanitization tests

**File:** `api/tests/test_highlights.py`
**Action:** Create
**Details:**

1. `test_sanitize_preserves_mark_tags()` -- Input with `<mark>keyword</mark>` is unchanged.

2. `test_sanitize_strips_script_tags()` -- Input with `<script>alert('xss')</script>` returns text without the script tag.

3. `test_sanitize_strips_html_preserving_text()` -- Input with `<b>bold</b> and <mark>highlight</mark>` returns `bold and <mark>highlight</mark>`.

4. `test_sanitize_handles_nested_tags()` -- Input with `<div><mark>word</mark></div>` returns `<mark>word</mark>`.

5. `test_sanitize_empty_string()` -- Empty input returns empty string.

**Verify:** `python -m pytest api/tests/test_highlights.py -x -v` -- all 5 tests pass.

### Wave 2: Integrate into Search Pipeline + Exact Match

#### Task 2.1: Add ts_headline to hybrid search results and wire facets

**Files:**
- `api/search/hybrid.py` (edit)
- `api/routers/search.py` (edit)

**Action:** Edit
**Details:**

In `api/search/hybrid.py`:
1. Add `ts_headline` to the final SELECT of the hybrid search SQL, applied AFTER ranking and pagination (on the final result set only, not on all candidates -- this is critical for performance per Pitfall 2):

```sql
ts_headline('english',
    coalesce(f.description, f.title),
    websearch_to_tsquery('english', %(query)s),
    %(ts_headline_options)s
) AS snippet
```

Add `ts_headline_options` to the params dict using the constant from `highlights.py`.

2. When `params.q` is empty (browse mode), set snippet to a truncated description: `LEFT(coalesce(f.description, f.title, ''), 200) AS snippet`.

3. After getting search results, call `sanitize_snippet()` on each row's snippet.

In `api/routers/search.py`:
1. Import and call `execute_facet_counts()` with the same filter clause.
2. Populate `SearchResponse.facets` with the facet results.
3. Extract `total_count` properly from the search results.

The flow in the router (already partially set up in Plan 3-02) becomes:
```python
# filter_clause and filter_params already built in Plan 3-02's router code
# Just add the facet call after the search call:
facets = execute_facet_counts(conn, filter_clause, filter_params)
# Build response with facets instead of empty FacetCounts()
```

Note: `build_filter_clause` is already called once in the router (Plan 3-02) and the result is passed to `execute_hybrid_search`. Reuse the same `filter_clause` and `filter_params` for `execute_facet_counts` — do NOT call `build_filter_clause` again.

**Verify:** `python -m pytest api/tests/ -x -q` -- all tests still pass.

#### Task 2.2: Implement exact match mode

**File:** `api/search/hybrid.py` (edit)
**Action:** Edit
**Details:**

Add `execute_exact_search(conn, params: SearchRequest, filter_clause: str, filter_params: dict) -> tuple[list[dict], int]` that handles `mode="exact"`:

```sql
WITH filtered AS (
    SELECT id, title, description, source_portal, closing_date,
           province, value_min, value_max, posting_date,
           classification_codes, source_listing_id
    FROM listings
    WHERE {filter_clause}
),
matched AS (
    SELECT id,
           CASE WHEN title ILIKE '%%' || %(query)s || '%%' THEN 0
                WHEN source_listing_id ILIKE '%%' || %(query)s || '%%' THEN 1
                ELSE 2
           END AS match_rank
    FROM filtered
    WHERE
        title ILIKE '%%' || %(query)s || '%%'
        OR description ILIKE '%%' || %(query)s || '%%'
        OR source_listing_id ILIKE '%%' || %(query)s || '%%'
),
total AS (
    SELECT COUNT(*) AS cnt FROM matched
)
SELECT
    f.id, f.title, f.description, f.closing_date,
    f.province, f.value_min, f.value_max, f.posting_date,
    f.classification_codes,
    p.name AS portal_name,
    m.match_rank,
    ts_headline('english',
        coalesce(f.description, f.title),
        phraseto_tsquery('english', %(query)s),
        %(ts_headline_options)s
    ) AS snippet,
    t.cnt AS total_count
FROM matched m
JOIN filtered f ON m.id = f.id
JOIN portals p ON f.source_portal = p.id
CROSS JOIN total t
ORDER BY m.match_rank, f.closing_date DESC NULLS LAST
LIMIT %(page_size)s OFFSET %(offset)s;
```

Update the search router to dispatch to `execute_exact_search` when `mode="exact"`.

Note: `%%` is the psycopg2 escape for a literal `%` in parameterized queries.

**Verify:** `python -m pytest api/tests/test_exact_match.py -x -v` passes.

#### Task 2.3: Write exact match tests

**File:** `api/tests/test_exact_match.py`
**Action:** Create
**Details:**

1. `test_exact_match_uses_ilike()` -- Mock cursor, call with `mode="exact", q="EN578-200001"`. Assert SQL contains `ILIKE`.

2. `test_exact_match_searches_source_listing_id()` -- Assert SQL contains `source_listing_id ILIKE`.

3. `test_exact_match_title_ranked_higher()` -- Assert `match_rank` CASE puts title matches (0) before description matches (2).

4. `test_exact_match_skips_embedding()` -- Assert `embed_query` is NOT called when mode is exact.

5. `test_exact_match_applies_filters()` -- Pass regions filter. Assert the filter clause appears in the SQL.

**Verify:** `python -m pytest api/tests/test_exact_match.py -x -v` -- all 5 tests pass.

## Plan Verification

Run all tests:
1. `python -m pytest api/tests/ -x -q` -- all tests pass (total should be ~45+ tests)
2. `python -c "from api.search.facets import execute_facet_counts; print('Facets OK')"` -- imports
3. `python -c "from api.search.highlights import sanitize_snippet, TS_HEADLINE_OPTIONS; print('Highlights OK')"` -- imports
4. Verify search response model includes facets: `python -c "from api.models.response import SearchResponse; sr = SearchResponse(); print(type(sr.facets))"` -- prints FacetCounts class
