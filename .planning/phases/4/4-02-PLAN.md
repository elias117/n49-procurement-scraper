---
phase: 4-web-application
plan: 02
type: execute
wave: 2
depends_on: ["4-01"]
files_modified:
  - web/src/lib/search-params.ts
  - web/src/hooks/use-search.ts
  - web/src/components/search/search-bar.tsx
  - web/src/components/search/filter-sidebar.tsx
  - web/src/components/search/results-list.tsx
  - web/src/components/search/result-card.tsx
  - web/src/components/search/pagination.tsx
  - web/src/components/search/sort-controls.tsx
  - web/src/app/dashboard/page.tsx
autonomous: true
requirements:
  - DASH-01
  - DASH-08

must_haves:
  truths:
    - "User sees paginated listing results after navigating to /dashboard"
    - "User can type a search query and results update after debounce"
    - "User can filter by region, portal, date ranges, value range, classification codes, and include_closed toggle"
    - "Sidebar filters are always visible (Amazon-style layout)"
    - "Result cards show title, source portal, closing date, posting date, province, contract value range, classification codes, status, and description snippet"
    - "Missing values display 'Value not disclosed' or 'Not specified' (never blank)"
    - "Current search + filters + sort + page are encoded in the URL"
    - "Copying and pasting the URL into a new tab reproduces the same search results"
    - "Browser back/forward navigates search history"
    - "Pagination controls allow navigating between pages"
    - "Sort controls allow sorting by relevance, posting date, closing date, or value"
  artifacts:
    - path: "web/src/lib/search-params.ts"
      provides: "nuqs parser definitions for all search parameters"
      contains: "searchParamsParsers"
    - path: "web/src/hooks/use-search.ts"
      provides: "Search state + data fetching hook"
      exports: ["useSearch"]
    - path: "web/src/components/search/filter-sidebar.tsx"
      provides: "Sidebar filter panel with all 6 filter dimensions"
      min_lines: 80
    - path: "web/src/components/search/result-card.tsx"
      provides: "Decision-dense result card with all required fields"
      min_lines: 40
    - path: "web/src/app/dashboard/page.tsx"
      provides: "Search page assembling all search components"
      min_lines: 30
  key_links:
    - from: "web/src/hooks/use-search.ts"
      to: "/api/search"
      via: "fetch with URL params built from nuqs state"
      pattern: "fetch.*api/search"
    - from: "web/src/hooks/use-search.ts"
      to: "web/src/lib/search-params.ts"
      via: "useQueryStates(searchParamsParsers)"
      pattern: "useQueryStates.*searchParamsParsers"
    - from: "web/src/app/dashboard/page.tsx"
      to: "web/src/hooks/use-search.ts"
      via: "useSearch hook"
      pattern: "useSearch"
    - from: "web/src/components/search/filter-sidebar.tsx"
      to: "web/src/hooks/use-search.ts"
      via: "setParams from useSearch"
      pattern: "setParams"
---

<objective>
Build the core search page with URL-synced state, debounced search bar, persistent sidebar filters (regions, portals, date ranges, value range, classification codes, include_closed), decision-dense result cards, server-side pagination, and sort controls. All search state is encoded in the URL for shareable links.

Purpose: The search page is the primary interface for the BD team. This is where they spend 90% of their time. Every filter change, search query, sort, and page navigation must be reflected in the URL so searches are shareable and browser back/forward works.

Output: Authenticated user can search, filter, sort, and paginate listings. URL state is shareable. Result cards show enough information for bid/no-bid decisions.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/4/4-CONTEXT.md
@.planning/phases/4/4-RESEARCH.md
@.planning/phases/4/4-01-SUMMARY.md
@api/routers/search.py
@api/models/response.py
@api/models/request.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Search params, useSearch hook, and search bar with debounce</name>
  <files>
    web/src/lib/search-params.ts
    web/src/hooks/use-search.ts
    web/src/components/search/search-bar.tsx
  </files>
  <action>
    1. Create `web/src/lib/search-params.ts`:
       - Import all nuqs parsers: parseAsString, parseAsInteger, parseAsBoolean, parseAsArrayOf, parseAsFloat, parseAsIsoDateTime, parseAsStringLiteral
       - Export searchParamsParsers object with ALL search parameters matching the FastAPI /search endpoint:
         - q: parseAsString.withDefault("")
         - mode: parseAsStringLiteral(["hybrid", "exact"] as const).withDefault("hybrid")
         - page: parseAsInteger.withDefault(1)
         - page_size: parseAsInteger.withDefault(25)
         - sort_by: parseAsStringLiteral(["relevance", "posting_date", "closing_date", "value"] as const).withDefault("relevance")
         - sort_order: parseAsStringLiteral(["asc", "desc"] as const).withDefault("desc")
         - include_closed: parseAsBoolean.withDefault(false)
         - regions: parseAsArrayOf(parseAsString).withDefault([])
         - portals: parseAsArrayOf(parseAsString).withDefault([])
         - closing_date_from: parseAsIsoDateTime
         - closing_date_to: parseAsIsoDateTime
         - posting_date_from: parseAsIsoDateTime
         - posting_date_to: parseAsIsoDateTime
         - value_min: parseAsFloat
         - value_max: parseAsFloat
         - classification_codes: parseAsArrayOf(parseAsString).withDefault([])

    2. Create `web/src/hooks/use-search.ts`:
       - "use client"
       - Import useQueryStates from "nuqs" and searchParamsParsers
       - Import SearchResponse from types
       - Call useQueryStates(searchParamsParsers, { history: "push" }) — this enables browser back/forward
       - useEffect that triggers on params change:
         - Create AbortController for cancellation
         - Build URLSearchParams from current params (skip empty/default values to keep URLs clean)
         - For array params (regions, portals, classification_codes): append each value separately (FastAPI expects repeated query params)
         - For date params: only add if not null, use toISOString()
         - Fetch from `/api/search?${searchParams}` with abort signal
         - Set data (SearchResponse | null) and loading state
         - Cleanup: abort on unmount or params change
       - Return { params, setParams, data, loading, error }
       - IMPORTANT: Reset page to 1 when any filter changes (not when page itself changes). Provide a setFilter helper that wraps setParams and resets page.

    3. Create `web/src/components/search/search-bar.tsx`:
       - "use client" component
       - Local state for input value (NOT synced to URL on every keystroke — Pitfall 4 from research)
       - Initialize local state from params.q
       - Debounce: use useEffect with 300ms setTimeout to sync local input to params.q via setParams
       - Search icon (lucide-react Search) on the left
       - Clear button (X icon) when input has value
       - Mode toggle: hybrid vs exact search — use a simple toggle button or dropdown
       - Props: params and setParams from useSearch hook (or accept them directly)
       - When user clears or changes query, reset page to 1
       - Styling: full-width input with rounded corners, subtle border, focus ring
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/web && npx tsc --noEmit --pretty 2>&1 | tail -20</automated>
    <manual>Verify search-params.ts has all 16 params matching FastAPI endpoint, use-search.ts builds URLSearchParams correctly with array handling</manual>
  </verify>
  <done>
    - searchParamsParsers defines all 16 search parameters with correct nuqs parsers
    - useSearch hook fetches from /api/search with all params serialized correctly
    - useQueryStates uses history: "push" for browser back/forward support
    - Search bar debounces input (300ms) before syncing to URL
    - Mode toggle switches between hybrid and exact search
    - Page resets to 1 on filter/query changes
    - TypeScript compiles without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Filter sidebar, result cards, pagination, sort, and search page assembly</name>
  <files>
    web/src/components/search/filter-sidebar.tsx
    web/src/components/search/results-list.tsx
    web/src/components/search/result-card.tsx
    web/src/components/search/pagination.tsx
    web/src/components/search/sort-controls.tsx
    web/src/app/dashboard/page.tsx
  </files>
  <action>
    1. Create `web/src/components/search/filter-sidebar.tsx`:
       - "use client" component
       - Props: params and setParams from useSearch, facets (FacetCounts) from search response
       - Always visible sidebar (LOCKED DECISION: Amazon-style, no collapse)
       - Filter sections, each with a heading and controls:
         a. Regions/Provinces: Checkbox list populated from facets.provinces. Show count next to each. Check/uncheck updates params.regions.
         b. Source Portals: Checkbox list populated from facets.portals. Show count next to each. Check/uncheck updates params.portals.
         c. Posting Date: Two date inputs (from/to) for posting_date_from and posting_date_to
         d. Closing Date: Two date inputs (from/to) for closing_date_from and closing_date_to
         e. Contract Value Range: Two number inputs (min/max) for value_min and value_max
         f. Classification Codes: Text input that adds codes as tags/chips to params.classification_codes
         g. Include Closed: Checkbox toggle for include_closed param
       - "Clear all filters" button at the top that resets all filter params to defaults
       - Each filter change calls setParams with page reset to 1
       - Use shadcn/ui components: Checkbox (via label+input or shadcn checkbox), Input, Button, Label, Separator, ScrollArea
       - Facet counts from API response show next to each option (e.g., "Ontario (42)")
       - Width: w-64 or w-72, scrollable if content overflows

    2. Create `web/src/components/search/result-card.tsx`:
       - "use client" component
       - Props: listing (ListingResult from search response), onClick handler, isNew (boolean for "New" badge — wired in Plan 4-03, accept prop now)
       - LOCKED DECISION: Decision-dense card with ALL these fields:
         a. Title (prominent, clickable)
         b. Source portal name
         c. Status badge (open/closed/cancelled/awarded — use shadcn Badge with color variants)
         d. Closing date (formatted, or "Not specified" if null)
         e. Posting date (formatted, or "Not specified" if null)
         f. Province (or "Not specified" if null)
         g. Contract value range (formatted via formatCurrency, or "Value not disclosed" if both null)
         h. Classification codes (as small badges/chips, or omit section if empty array)
         i. Description snippet (rendered with keyword highlights — snippet contains <mark> tags from API, render with dangerouslySetInnerHTML for the snippet only, it's sanitized by bleach on the API side)
       - "New" badge: render shadcn Badge variant="destructive" or a custom green badge if isNew is true
       - LOCKED DECISION: Missing values shown explicitly — NEVER blank fields
       - Card styling: subtle border, hover shadow, cursor pointer, padding
       - Use formatDate and formatCurrency from lib/format.ts

    3. Create `web/src/components/search/results-list.tsx`:
       - "use client" component
       - Props: results (ListingResult[]), loading, onSelectListing (callback for opening detail — wired in 4-03), total_count, lastVisitedAt (optional string — wired in 4-03)
       - Maps over results and renders ResultCard for each
       - Shows total count: "X results found"
       - Loading state: render 5-6 skeleton cards (shadcn Skeleton component)
       - Empty state: "No listings found. Try adjusting your filters." message
       - Each card's isNew prop: compare listing.posting_date > lastVisitedAt (basic comparison, refined in 4-03)

    4. Create `web/src/components/search/pagination.tsx`:
       - "use client" component
       - Props: page (current), totalPages, onPageChange callback
       - Buttons: First, Previous, page numbers (show window of 5 around current), Next, Last
       - Disable Previous/First on page 1, Next/Last on last page
       - Use shadcn/ui Button components
       - Show "Page X of Y" text

    5. Create `web/src/components/search/sort-controls.tsx`:
       - "use client" component
       - Props: sort_by, sort_order, onSortChange callback
       - Dropdown (shadcn Select) for sort field: Relevance, Posting Date, Closing Date, Value
       - Toggle button for asc/desc
       - When sort changes, reset page to 1

    6. Update `web/src/app/dashboard/page.tsx`:
       - "use client" (needed for hooks)
       - Call useSearch() hook to get params, setParams, data, loading
       - Layout: flex row with sidebar on left, main content on right
       - Left: FilterSidebar with params, setParams, facets from data
       - Right column top: SearchBar + SortControls in a row
       - Right column main: ResultsList with results from data
       - Right column bottom: Pagination with page, totalPages, onPageChange
       - Pass total_count to ResultsList for display
       - The listing detail Sheet and "New" badge logic will be wired in Plan 4-03 — for now, onSelectListing can be a no-op or console.log
       - Responsive: On mobile (< lg), sidebar could stack above results or be collapsible (Claude's discretion per CONTEXT.md)
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/web && npm run build 2>&1 | tail -20</automated>
    <manual>Verify the dashboard page assembles all search components, filter sidebar has all 6 filter dimensions, result cards show all required fields</manual>
  </verify>
  <done>
    - Filter sidebar renders all 6 filter dimensions with facet counts from API
    - Result cards display all required fields: title, portal, dates, province, value, codes, status, snippet
    - Missing values show "Value not disclosed" or "Not specified" (never blank)
    - Pagination controls navigate between pages
    - Sort controls allow 4 sort options with asc/desc toggle
    - Search page assembles sidebar + search bar + sort + results + pagination
    - All filter/search/sort/page state is in the URL via nuqs
    - URL can be copied and pasted to reproduce search results
    - Browser back/forward navigates search history (nuqs history: "push")
    - `npm run build` succeeds
  </done>
</task>

</tasks>

<verification>
1. `cd web && npm run build` succeeds
2. Dashboard page imports and renders all search components
3. searchParamsParsers covers all 16 params matching FastAPI /search endpoint
4. useSearch hook builds correct URLSearchParams (verify array params use append, not set)
5. Filter sidebar has sections for: regions, portals, posting date, closing date, value range, classification codes, include_closed
6. Result card displays all 9 required fields from CONTEXT.md locked decisions
7. No blank fields — all null values show explicit labels
</verification>

<success_criteria>
- Search page loads and fetches results from /api/search
- All 16 search parameters sync bidirectionally between URL and UI
- Sidebar filters show facet counts and filter results on change
- Result cards are decision-dense with all required fields
- Pagination, sort, and search all work and update URL
- Shareable: URL copy-paste reproduces identical search state
- Browser back/forward navigates search history
</success_criteria>

<output>
After completion, create `.planning/phases/4/4-02-SUMMARY.md`
</output>
