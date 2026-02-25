---
phase: 4-web-application
plan: 03
type: execute
wave: 3
depends_on: ["4-01", "4-02"]
files_modified:
  - web/src/hooks/use-listing-detail.ts
  - web/src/components/search/listing-detail.tsx
  - web/src/components/layout/freshness.tsx
  - web/src/app/dashboard/page.tsx
  - web/src/app/dashboard/layout.tsx
autonomous: true
requirements:
  - DASH-02
  - DASH-03
  - DASH-05
  - DASH-06
  - DASH-09

must_haves:
  truths:
    - "Clicking a result card opens a slide-out Sheet with full listing detail"
    - "Listing detail shows all fields in correct order: title, status, dates, description, documents, contact card, source link"
    - "Source portal link is a prominent 'View on Source Portal' button (not a small link)"
    - "Documents section shows attachment name, type, date, and download/view link"
    - "Contact info has clickable mailto: and tel: links"
    - "Missing fields show 'Not specified' (never blank)"
    - "Results list stays visible behind the slide-out panel"
    - "Listings with posting_date after user's last_visited_at are badged as 'New'"
    - "New badge resets on next dashboard open (last_visited_at updated AFTER reading old value)"
    - "Data freshness indicator in nav shows when listings were last updated"
  artifacts:
    - path: "web/src/hooks/use-listing-detail.ts"
      provides: "Fetch listing detail by ID"
      exports: ["useListingDetail"]
    - path: "web/src/components/search/listing-detail.tsx"
      provides: "Sheet slide-out with full listing detail"
      min_lines: 80
    - path: "web/src/components/layout/freshness.tsx"
      provides: "Data freshness indicator component"
      min_lines: 15
  key_links:
    - from: "web/src/hooks/use-listing-detail.ts"
      to: "/api/listings/{id}"
      via: "fetch on listing selection"
      pattern: "fetch.*api/listings"
    - from: "web/src/app/dashboard/page.tsx"
      to: "web/src/components/search/listing-detail.tsx"
      via: "ListingDetailSheet with selectedId state"
      pattern: "ListingDetailSheet"
    - from: "web/src/app/dashboard/layout.tsx"
      to: "/api/users/{id}/last-visit"
      via: "GET then PUT on dashboard mount"
      pattern: "last-visit"
    - from: "web/src/components/layout/freshness.tsx"
      to: "/api/health/freshness"
      via: "fetch freshness data"
      pattern: "health/freshness"
---

<objective>
Build the listing detail Sheet slide-out panel (with documents, contact info, source link), implement "New" badge logic using last_visited_at read-then-update pattern, and add the data freshness indicator to the navigation bar.

Purpose: The detail panel completes the core search workflow (browse -> click -> evaluate -> act). "New" badges help the team spot fresh opportunities. The freshness indicator builds confidence that data is current.

Output: Clicking a result card opens a slide-out with full listing details. New listings are badged. Nav shows data freshness.
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
@.planning/phases/4/4-02-SUMMARY.md
@web/src/types/listing.ts
@web/src/types/search.ts
@web/src/types/health.ts
@web/src/lib/api.ts
@web/src/lib/format.ts
@web/src/hooks/use-search.ts
@web/src/components/search/result-card.tsx
@web/src/components/search/results-list.tsx
@web/src/app/dashboard/page.tsx
@web/src/app/dashboard/layout.tsx
@web/src/components/layout/nav.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Listing detail Sheet slide-out with documents, contacts, and source link</name>
  <files>
    web/src/hooks/use-listing-detail.ts
    web/src/components/search/listing-detail.tsx
    web/src/app/dashboard/page.tsx
  </files>
  <action>
    1. Create `web/src/hooks/use-listing-detail.ts`:
       - "use client"
       - Export useListingDetail(listingId: string | null) hook
       - When listingId changes and is not null, fetch from `/api/listings/${listingId}`
       - AbortController for cleanup
       - Return { listing: ListingDetail | null, loading: boolean, error: string | null }
       - Clear listing data when listingId becomes null

    2. Create `web/src/components/search/listing-detail.tsx`:
       - "use client" component
       - Import shadcn/ui Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription
       - Import shadcn/ui Badge, Button, Separator, ScrollArea
       - Import lucide-react icons: ExternalLink, Mail, Phone, FileText, Calendar, MapPin, DollarSign
       - Import formatDate, formatCurrency from lib/format.ts
       - Props: listing (ListingDetail | null), open (boolean), onClose, loading (boolean)
       - Sheet opens from the right side, width ~600px (sm:max-w-[600px])
       - SheetContent has overflow-y-auto for scrolling
       - LOCKED DECISION — Layout order top to bottom:
         a. TITLE: SheetTitle with listing title
         b. STATUS: Badge showing listing.status (color-coded: open=green, closed=gray, cancelled=red, awarded=blue)
         c. Portal name as SheetDescription
         d. DATES section: Grid with posting date and closing date. Use formatDate — shows "Not specified" if null.
            Also show amended_date if present.
         e. METADATA section: Province (or "Not specified"), value range (formatCurrency — "Value not disclosed" if both null), classification codes as Badge chips
         f. DESCRIPTION section: Heading + whitespace-pre-wrap paragraph. Show "Not specified" if null/empty.
         g. DOCUMENTS section (DASH-09): Only render if listing.documents is non-empty array.
            Each document: clickable link with FileText icon, document name, type label (RFP/amendment/addendum/Document), date if available.
            Links open in new tab (target="_blank" rel="noopener noreferrer").
            Show "No documents available" if documents is null or empty array.
         h. CONTACT CARD (DASH-09): Only render if listing.contact_info is not null.
            LOCKED DECISION: Contact info is actionable:
            - Name: plain text
            - Email: <a href="mailto:..."> with Mail icon, click-to-email
            - Phone: <a href="tel:..."> with Phone icon, click-to-call
            - Title/role if available
            Show "No contact information available" if contact_info is null.
         i. SOURCE LINK (DASH-03): LOCKED DECISION: "View on Source Portal" is a PROMINENT BUTTON, not a small link.
            Full-width shadcn Button (size="lg") wrapping an anchor tag.
            Opens in new tab. ExternalLink icon.
            Show source portal name in button text: "View on {source_portal_name}"
            If source_url is null, show disabled button with "Source URL not available"
       - Loading state: Show Skeleton components in the Sheet layout while loading
       - LOCKED DECISION: Missing values always show explicit labels ("Not specified", "Value not disclosed", "No documents available", etc.)

    3. Update `web/src/app/dashboard/page.tsx`:
       - Add state: selectedListingId (string | null), initialized to null
       - Call useListingDetail(selectedListingId)
       - Pass onSelectListing callback to ResultsList that sets selectedListingId
       - Render ListingDetailSheet with:
         - listing from useListingDetail
         - open = selectedListingId !== null
         - onClose sets selectedListingId to null
         - loading from useListingDetail
       - IMPORTANT: The results list must remain visible and interactive behind the Sheet overlay
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/web && npx tsc --noEmit --pretty 2>&1 | tail -20</automated>
    <manual>Verify listing-detail.tsx follows the locked layout order (title, status, dates, description, documents, contact, source) and all missing-value labels are present</manual>
  </verify>
  <done>
    - Clicking a result card opens Sheet slide-out with full listing detail
    - Detail panel shows all fields in locked layout order
    - Documents section renders attachment links with name, type, date (DASH-09)
    - Contact card has click-to-email and click-to-call links (DASH-09)
    - "View on Source Portal" is a prominent full-width button (DASH-03)
    - Missing values show explicit labels (never blank)
    - Results list stays visible behind the Sheet overlay
    - TypeScript compiles without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: "New" badges with last_visited_at logic and data freshness indicator</name>
  <files>
    web/src/components/layout/freshness.tsx
    web/src/app/dashboard/layout.tsx
    web/src/app/dashboard/page.tsx
    web/src/components/search/results-list.tsx
  </files>
  <action>
    1. Create `web/src/components/layout/freshness.tsx`:
       - "use client" component
       - On mount, fetch from `/api/health/freshness` to get { last_updated: string | null }
       - Display in a compact format suitable for the nav bar: "Updated X ago" or "Updated: [date]"
       - Use formatRelativeTime from lib/format.ts (date-fns formatDistanceToNow)
       - If last_updated is null, show "No data yet"
       - Auto-refresh every 5 minutes (setInterval)
       - Styling: small text, muted foreground color, optional clock icon (lucide Clock)

    2. Update `web/src/app/dashboard/layout.tsx`:
       - Import and render Freshness component in the nav area (either inside Nav or alongside it)
       - The freshness indicator should be visible on both the search page and health page
       - If the layout is a server component, make Freshness a client component that renders inside it

    3. Implement "New" badge logic in dashboard/page.tsx:
       - CRITICAL PATTERN (Pitfall 5 from research): Read last_visited_at BEFORE updating it
       - On dashboard page mount (useEffect, runs once):
         a. Get the user's session (from Auth.js useSession or from the auth() call)
         b. GET /api/users/{userId}/last-visit — store the PREVIOUS last_visited_at value in state
         c. THEN PUT /api/users/{userId}/last-visit — update it to NOW for next visit
         d. The stored previous value is used for "New" badge comparison throughout this session
       - Pass lastVisitedAt (the PREVIOUS value) to ResultsList component
       - IMPORTANT: Use the internal API URL for server-side calls, or use client-side fetch through /api/ proxy

    4. Update `web/src/components/search/results-list.tsx`:
       - Accept lastVisitedAt prop (string | null)
       - For each result, compute isNew: if lastVisitedAt is not null AND listing.posting_date is not null AND new Date(listing.posting_date) > new Date(lastVisitedAt) then isNew = true
       - Pass isNew to each ResultCard component

    5. Ensure ResultCard renders the "New" badge:
       - The ResultCard already accepts isNew prop (from Plan 4-02)
       - Verify it renders a visible badge: shadcn Badge with a distinctive color (green or blue) showing "New"
       - Badge should be positioned near the title or in the top-right corner of the card
       - LOCKED DECISION: Badge is not dismissible — stays on all qualifying listings until next dashboard open

    6. Wire up the user ID for last-visit API calls:
       - Import useSession from "next-auth/react" in the dashboard page
       - The session.user.id was added to the session in Auth.js callbacks (Plan 4-01)
       - Need SessionProvider: If not already in place, add SessionProvider to the dashboard layout
       - Actually, check if Auth.js v5 requires SessionProvider for client components. If using JWT strategy, useSession requires SessionProvider wrapper.
       - Add SessionProvider from "next-auth/react" in the dashboard layout (wrap children)
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/web && npm run build 2>&1 | tail -20</automated>
    <manual>Verify the last_visited_at read-before-update pattern: GET happens before PUT, and the old value is stored for badge comparison</manual>
  </verify>
  <done>
    - Freshness indicator shows "Updated X ago" in the nav area (DASH-05)
    - "New" badges appear on listings with posting_date after user's previous last_visited_at (DASH-06)
    - last_visited_at is read BEFORE being updated (badges don't disappear on load)
    - Badge is not dismissible and resets on next dashboard open
    - SessionProvider wired for useSession in client components
    - `npm run build` succeeds
  </done>
</task>

</tasks>

<verification>
1. `cd web && npm run build` succeeds
2. ListingDetailSheet renders all fields in locked layout order
3. Documents section renders clickable links with name, type, date
4. Contact card has mailto: and tel: links
5. "View on Source Portal" is a full-width prominent button
6. Freshness component fetches from /api/health/freshness
7. "New" badge logic: GET last-visit -> store old value -> PUT last-visit -> use old value for comparison
8. ResultCard renders "New" badge when isNew is true
</verification>

<success_criteria>
- Clicking a result opens a slide-out Sheet with full listing detail in correct layout order
- Documents and contact info render with actionable links (DASH-02, DASH-03, DASH-09)
- "View on Source Portal" is a prominent button, not a small link (DASH-03)
- Listings posted since user's last visit are badged as "New" (DASH-06)
- Data freshness indicator visible in nav area (DASH-05)
- All missing values show explicit labels (never blank)
</success_criteria>

<output>
After completion, create `.planning/phases/4/4-03-SUMMARY.md`
</output>
