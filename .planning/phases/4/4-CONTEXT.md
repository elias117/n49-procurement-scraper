# Phase 4: Web Application - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Next.js dashboard with auth, search UI, listing detail, and scraper health page. The BD team (3 users) can log in, search all 63 portals from one dashboard, view listing details, and monitor scraper health. The platform becomes usable for daily work. Replaces the current Express stub in `web/`.

Consumes the existing FastAPI search API (`GET /search`) which returns hybrid keyword + semantic results with facet counts, keyword highlights, and full filter support.

</domain>

<decisions>
## Implementation Decisions

### Search results layout & information density
- Result cards are **decision-dense** — enough info to make a bid/no-bid call without clicking into the listing
- Each result card shows: title, source portal name, closing date, posting date, province, contract value range, classification codes, status, and a longer description snippet with keyword highlights
- **Sidebar filters always visible** (Amazon-style layout) — the team filters frequently, no extra click to access
- Missing values shown explicitly: "Value not disclosed", "Not specified" — never blank, so users know it's not a bug

### Listing detail view
- **Side panel (slide-out)** — results list stays visible behind it, supports rapid bid/no-bid scanning across multiple listings
- Layout order top to bottom: title, status, dates (posting/closing), description, documents section (RFPs, amendments, addenda with type labels), contact card, source link
- **Contact info is actionable** — prominent card with click-to-email and click-to-call links. BD team acts on contacts immediately.
- **"View on source portal" is a prominent button**, not a small link — the team always clicks through to verify on the original portal before acting
- Documents section shows attachment name, type (RFP/amendment/addendum), date if available, and download/view link

### "New" badge logic & user tracking
- 3 individual user accounts (simple username/password)
- **"Last visit" = last time that user opened the dashboard** (not login time, not per-listing clicks)
- "New" badge appears on any listing with `posting_date` after the user's `last_visited_at` timestamp
- Badge is **not dismissible** — stays on all qualifying listings until the user's next dashboard open resets their timestamp
- No per-listing read tracking needed — just a single `last_visited_at` column per user
- Opening the dashboard updates `last_visited_at` for that user

### Scraper health page
- **Top-level nav item** — all 3 team members have access, not hidden behind admin
- Full diagnostic detail per portal: last run date, success/fail status, listings found/new/updated, run duration, error messages
- Failure counts visible (e.g., "Failed 3 of last 5 runs") alongside color status
- Staleness thresholds from Phase 2 reflected visually: 1 missed night = no indicator, 3 consecutive failures = amber, 7+ days stale = red
- **Purely informational** — no action buttons (retry, disable, re-enable). Developer handles fixes outside the dashboard.

### URL-encoded search state
- Current search query + all active filters + sort + page encoded in the URL (success criteria #4)
- A user can copy the URL and share it — recipient sees identical results
- Browser back/forward navigates search history naturally

### Claude's Discretion
- Next.js app router vs pages router
- CSS framework / component library choice
- Authentication implementation (JWT, session cookies, etc.)
- Responsive breakpoints and mobile behavior
- Loading states, skeleton screens, error boundaries
- Exact color palette and visual design
- Side panel width and animation
- Pagination controls style

</decisions>

<specifics>
## Specific Ideas

- Sidebar filters always visible like Amazon/Shopify product filtering
- Side panel for listing detail like a mail client (click item, detail slides in from right, list stays visible)
- Contact card should feel actionable — email and phone are tappable/clickable, not just displayed text
- "View on source portal" button should be visually prominent — it's part of the core workflow, not an afterthought
- Explicit "Value not disclosed" / "Not specified" labels for missing data to build trust that the system is working correctly

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4*
*Context gathered: 2026-02-24*
