# Phase 3 Context: Search Layer

## Query Interpretation

- **Search box is hybrid only** — no auto-extraction of filters from natural language. The search box runs combined keyword + semantic search (RRF). Structured filters (region, date range, value range, category, portal, sort) are separate dedicated controls in the dashboard.
- **Two search modes:** hybrid (default) and exact match (toggle). Exact match is for tender numbers or specific titles. No other modes.
- **RRF weighting handles short vs long queries implicitly** — short queries naturally get stronger keyword hits, longer queries get better semantic matches. Tune `k` parameters after real data exists; don't over-engineer upfront.

## API Response Shape

- **List result fields:** title, source portal, closing date, region, contract value (if available), 1-2 line description snippet with keyword highlights (bold matched terms).
- **Relevance score is internal** — used for sorting, never surfaced to the user as a raw number.
- **Keyword highlights required** — return highlighted snippets showing why a result matched. Standard search UX for trust and scannability.
- **Facet counts required** — return counts per filter value (e.g., "Ontario (42), Federal (31)") alongside results. At 1-5K listings, overhead is negligible (`GROUP BY` counts).
- **Offset-based pagination** — `LIMIT/OFFSET`, page size 25 or 50. No cursor-based pagination needed at this data volume. Users can jump to any page.

## Expired/Closed Listing Visibility

- **"Open" definition:** `closing_date > now() - 48 hours`. 48-hour grace period accounts for slow government portal updates.
- **No closing date = perpetually open** — always included in default results. Standing offers and supply arrangements are high-value and must not be hidden.
- **Expired listings are searchable** — "Include closed" toggle, off by default. Past listings have competitive intelligence value.
- **Amendment handling:** `closing_date` (current/authoritative) is what the API filters on. Store `original_closing_date` as a separate field so users can see extensions, but filtering uses current date only.

## Filter Behavior on Missing Data

- **AND across dimensions, OR within dimension** — "Ontario OR Quebec" + "closing next 30 days" + "$100K-$500K" applies all three constraints with AND.
- **Missing contract value + value filter active = excluded.** Deliberate filtering should not be diluted by null-value listings. They appear when no value filter is set.
- **Missing category + category filter active = excluded.** Same logic as value — deliberate filter, don't show noise.
- **National/unspecified region + province filter active = included.** National federal tenders apply everywhere. "National" is also a selectable region option in its own right.

## Schema Note

- Add `original_closing_date` field to listings table (or handle in API layer) to support amendment tracking per decisions above.

## Deferred Ideas

None captured during this discussion.
