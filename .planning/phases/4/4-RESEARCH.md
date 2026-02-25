# Phase 4: Web Application - Research

**Researched:** 2026-02-24
**Domain:** Next.js dashboard, authentication, URL state management, data tables, side panels
**Confidence:** HIGH

## Summary

Phase 4 replaces the Express stub in `web/` with a full Next.js 15 dashboard that lets the 3 BD team members log in, search all 63 portals, view listing details in a slide-out panel, and monitor scraper health. The frontend consumes the existing FastAPI search API at `/api/search` and needs 4 new API endpoints added to FastAPI: listing detail, scraper health, auth login, and last-visit tracking.

The standard stack is Next.js 15 (App Router) + shadcn/ui + Tailwind CSS + nuqs for URL state + Auth.js v5 (Credentials provider with JWT sessions). The search page is the core -- an Amazon-style layout with persistent sidebar filters, decision-dense result cards, and a Sheet slide-out for listing detail. All search/filter state syncs to URL via nuqs so searches are shareable. The Next.js app runs in standalone Docker mode on node:20-alpine, fitting into the existing Docker Compose + nginx reverse proxy architecture.

**Primary recommendation:** Use Next.js 15 App Router with client-side data fetching for the search page (URL state drives fetch calls), server-side auth via Auth.js v5 middleware, and shadcn/ui components throughout. The search page is a single client component tree that owns filter state via nuqs and fetches from `/api/search` on state change. New FastAPI endpoints handle listing detail, health data, auth, and visit tracking.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Result cards are decision-dense -- enough info to make a bid/no-bid call without clicking into the listing
- Each result card shows: title, source portal name, closing date, posting date, province, contract value range, classification codes, status, and a longer description snippet with keyword highlights
- Sidebar filters always visible (Amazon-style layout)
- Missing values shown explicitly: "Value not disclosed", "Not specified"
- Side panel (slide-out) for listing detail -- results list stays visible behind it
- Layout order: title, status, dates, description, documents section, contact card, source link
- Contact info is actionable (click-to-email, click-to-call)
- "View on source portal" is a prominent button
- Documents section shows attachment name, type, date, download/view link
- 3 individual user accounts (simple username/password)
- "Last visit" = last time that user opened the dashboard
- "New" badge on listings with posting_date after user's last_visited_at
- Badge is not dismissible -- resets on next dashboard open
- Single last_visited_at column per user
- Scraper health page: top-level nav item, accessible by all users
- Full diagnostic detail: last run date, success/fail, listings found/new/updated, duration, error messages
- Failure counts: "Failed 3 of last 5 runs"
- Staleness thresholds: 3 consecutive failures = amber, 7+ days stale = red
- Purely informational -- no action buttons
- Current search query + all active filters + sort + page encoded in URL
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | User can view paginated listing results in a searchable table | Search page with nuqs URL state, TanStack Table server-side pagination, fetching from existing `/api/search` endpoint |
| DASH-02 | User can click a listing to view full detail including all extracted fields | shadcn/ui Sheet component slide-out panel, new `/api/listings/{id}` FastAPI endpoint |
| DASH-03 | Listing detail includes a link to the original source portal page | `source_url` field from listings table rendered as prominent button in Sheet |
| DASH-04 | User can log in with username/password (simple credentials auth) | Auth.js v5 Credentials provider, JWT sessions, bcrypt password hashing, new `users` table + FastAPI auth endpoints |
| DASH-05 | Dashboard displays data freshness indicator | Query `MAX(completed_at)` from scrape_runs, display in header/nav area |
| DASH-06 | Listings posted since user's last visit are badged as "New" | `last_visited_at` column on users table, compare with `posting_date`, shadcn/ui Badge component |
| DASH-07 | User can view scraper health page per-portal | New `/api/health/portals` endpoint aggregating scrape_runs, dedicated `/health` page |
| DASH-08 | Filter state synced to URL so searches are shareable | nuqs `useQueryStates` with all search params, `history: 'push'` for back/forward |
| DASH-09 | Listing detail displays document attachments and contact info | `documents` (JSONB) and `contact_info` (JSONB) fields rendered in Sheet detail view |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | ^15.1 | React framework with App Router | Stable LTS, full RSC support, standalone Docker output. Next.js 16 exists but is too new; 15 is battle-tested. |
| react / react-dom | ^19.0 | UI rendering | Required by Next.js 15, stable release |
| next-auth | 5.x (beta tag) | Authentication | Auth.js v5 is the standard for Next.js App Router auth. Install via `npm install next-auth@beta`. Credentials provider with JWT sessions. |
| nuqs | ^2.8 | URL search param state management | Used by Vercel, Sentry, Supabase. 6KB gzipped. Type-safe URL state that syncs with React state. Featured at Next.js Conf 2025. |
| @tanstack/react-table | ^8.21 | Headless table logic | Powers tables at Linear, Notion. Server-side pagination via `manualPagination`. |
| tailwindcss | ^4.0 | Utility-first CSS | Ships with Next.js 15 via `create-next-app --tailwind`. shadcn/ui requires it. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn/ui | latest (CLI) | Pre-built accessible components | Not an npm package -- installed via `npx shadcn@latest init` then `npx shadcn@latest add [component]`. Uses Radix UI primitives + Tailwind CSS. |
| bcryptjs | ^2.4 | Password hashing | Pure JS bcrypt (no native deps). Used in auth `authorize` callback. Prefer over `bcrypt` for Alpine Docker compat. |
| zod | ^3.23 | Schema validation | Validate login form, API responses, search params. Already a peer dep of Auth.js v5. |
| lucide-react | ^0.460 | Icons | Default icon library for shadcn/ui. Ships with shadcn init. |
| date-fns | ^4.1 | Date formatting | `formatDistanceToNow`, `format` for relative timestamps and date display. |
| clsx + tailwind-merge | latest | Conditional classnames | Installed automatically by shadcn/ui init as the `cn()` utility. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| nuqs | Manual `useSearchParams` + `useRouter` | Manual approach requires verbose serialization/deserialization, no batching, no type safety. nuqs is 6KB and solves this completely. |
| shadcn/ui | Radix UI directly | More flexibility but requires building every component from scratch. shadcn/ui gives pre-styled, copy-paste components with full control. |
| @tanstack/react-table | Custom table markup | Works for simple tables but loses pagination model, sorting APIs, and column management that TanStack provides for free. |
| bcryptjs | bcrypt | Native `bcrypt` requires build tools in Alpine Docker. `bcryptjs` is pure JS, works everywhere, acceptable for 3 users. |
| Auth.js v5 | Custom JWT with jose | Auth.js handles session management, CSRF, cookie rotation, middleware integration. Hand-rolling auth for 3 users is still error-prone. |

### FastAPI Additions (Python side)

No new Python dependencies needed. The existing `psycopg2-binary`, `fastapi`, and `pydantic` stack handles the 4 new endpoints. Add `bcrypt` (Python) for password verification in the auth endpoint if hashing is done server-side, or use the existing `bcryptjs` in Next.js.

**Recommendation:** Hash passwords with `bcryptjs` in a Next.js server action/route handler and store hashed passwords in the `users` table. Auth stays entirely in the Next.js layer. FastAPI only needs listing detail and health endpoints (no auth endpoints needed on the Python side).

**Installation:**
```bash
# In web/ directory
npx create-next-app@latest . --ts --tailwind --eslint --app --src-dir --import-alias "@/*"
npm install next-auth@beta nuqs @tanstack/react-table bcryptjs date-fns zod
npm install -D @types/bcryptjs

# shadcn/ui init + components
npx shadcn@latest init
npx shadcn@latest add button input badge card sheet table select skeleton separator scroll-area tooltip dropdown-menu
```

## Architecture Patterns

### Recommended Project Structure

```
web/
├── Dockerfile                     # Multi-stage standalone build
├── next.config.ts                 # standalone output, rewrites /api -> api:8000
├── src/
│   ├── app/
│   │   ├── layout.tsx             # Root layout: NuqsAdapter + SessionProvider
│   │   ├── page.tsx               # Redirect to /dashboard
│   │   ├── login/
│   │   │   └── page.tsx           # Login form (public)
│   │   ├── dashboard/
│   │   │   ├── layout.tsx         # Dashboard shell: nav, auth guard, freshness indicator
│   │   │   ├── page.tsx           # Search page (main view)
│   │   │   └── health/
│   │   │       └── page.tsx       # Scraper health page
│   │   └── api/
│   │       └── auth/
│   │           └── [...nextauth]/
│   │               └── route.ts   # Auth.js route handlers
│   ├── auth.ts                    # Auth.js configuration (Credentials provider)
│   ├── middleware.ts              # Auth middleware -- protect /dashboard/*
│   ├── components/
│   │   ├── ui/                    # shadcn/ui components (auto-generated)
│   │   ├── search/
│   │   │   ├── search-bar.tsx     # Search input with mode toggle
│   │   │   ├── filter-sidebar.tsx # Sidebar filters (regions, portals, dates, value)
│   │   │   ├── results-list.tsx   # Result cards with "New" badges
│   │   │   ├── result-card.tsx    # Individual result card
│   │   │   ├── listing-detail.tsx # Sheet slide-out with full listing
│   │   │   └── pagination.tsx     # Page navigation controls
│   │   ├── health/
│   │   │   ├── portal-table.tsx   # Health status table
│   │   │   └── status-badge.tsx   # Color-coded status indicator
│   │   ├── layout/
│   │   │   ├── nav.tsx            # Top navigation bar
│   │   │   └── freshness.tsx      # Data freshness indicator
│   │   └── login-form.tsx         # Login form component
│   ├── hooks/
│   │   ├── use-search.ts          # Search state + data fetching hook
│   │   └── use-listing-detail.ts  # Listing detail fetching hook
│   ├── lib/
│   │   ├── api.ts                 # Fetch helpers for FastAPI endpoints
│   │   ├── search-params.ts       # nuqs parser definitions for all search params
│   │   ├── utils.ts               # cn() utility (shadcn/ui default)
│   │   └── format.ts              # Date/currency formatting helpers
│   └── types/
│       ├── search.ts              # SearchResponse, ListingResult, FacetCounts
│       ├── listing.ts             # ListingDetail (full fields)
│       └── health.ts              # PortalHealth, ScrapeRun
├── public/                        # Static assets
└── components.json                # shadcn/ui config
```

### Pattern 1: URL-Synced Search with nuqs

**What:** All search state (query, filters, sort, page) lives in the URL via nuqs. The search page is a client component tree that reads state from URL and fetches data on change.

**When to use:** The search/dashboard page -- DASH-01, DASH-08.

**Example:**
```typescript
// src/lib/search-params.ts
import {
  parseAsString,
  parseAsInteger,
  parseAsBoolean,
  parseAsArrayOf,
  parseAsFloat,
  parseAsIsoDateTime,
  parseAsStringLiteral,
} from "nuqs"

export const searchParamsParsers = {
  q: parseAsString.withDefault(""),
  mode: parseAsStringLiteral(["hybrid", "exact"] as const).withDefault("hybrid"),
  page: parseAsInteger.withDefault(1),
  page_size: parseAsInteger.withDefault(25),
  sort_by: parseAsStringLiteral([
    "relevance", "posting_date", "closing_date", "value"
  ] as const).withDefault("relevance"),
  sort_order: parseAsStringLiteral(["asc", "desc"] as const).withDefault("desc"),
  include_closed: parseAsBoolean.withDefault(false),
  regions: parseAsArrayOf(parseAsString).withDefault([]),
  portals: parseAsArrayOf(parseAsString).withDefault([]),
  closing_date_from: parseAsIsoDateTime,
  closing_date_to: parseAsIsoDateTime,
  posting_date_from: parseAsIsoDateTime,
  posting_date_to: parseAsIsoDateTime,
  value_min: parseAsFloat,
  value_max: parseAsFloat,
  classification_codes: parseAsArrayOf(parseAsString).withDefault([]),
}

// src/hooks/use-search.ts
"use client"
import { useQueryStates } from "nuqs"
import { searchParamsParsers } from "@/lib/search-params"
import { useEffect, useState } from "react"
import type { SearchResponse } from "@/types/search"

export function useSearch() {
  const [params, setParams] = useQueryStates(searchParamsParsers, {
    history: "push",  // enables back/forward navigation
  })
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)

    const searchParams = new URLSearchParams()
    if (params.q) searchParams.set("q", params.q)
    searchParams.set("mode", params.mode)
    searchParams.set("page", String(params.page))
    searchParams.set("page_size", String(params.page_size))
    searchParams.set("sort_by", params.sort_by)
    searchParams.set("sort_order", params.sort_order)
    searchParams.set("include_closed", String(params.include_closed))
    params.regions.forEach(r => searchParams.append("regions", r))
    params.portals.forEach(p => searchParams.append("portals", p))
    // ... remaining params

    fetch(`/api/search?${searchParams}`, { signal: controller.signal })
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))

    return () => controller.abort()
  }, [params])

  return { params, setParams, data, loading }
}
```

### Pattern 2: Auth.js v5 Credentials Provider with JWT

**What:** Simple username/password auth with JWT sessions stored in cookies. Middleware protects all `/dashboard/*` routes.

**When to use:** DASH-04 (authentication).

**Example:**
```typescript
// src/auth.ts
import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import { compare } from "bcryptjs"
import { z } from "zod"

// Direct DB query for auth (only 3 users, no ORM needed)
async function getUser(username: string) {
  const res = await fetch(
    `${process.env.API_INTERNAL_URL}/auth/user?username=${encodeURIComponent(username)}`
  )
  if (!res.ok) return null
  return res.json()
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const parsed = z.object({
          username: z.string().min(1),
          password: z.string().min(1),
        }).safeParse(credentials)
        if (!parsed.success) return null

        const user = await getUser(parsed.data.username)
        if (!user) return null

        const passwordMatch = await compare(parsed.data.password, user.password_hash)
        if (!passwordMatch) return null

        return { id: user.id, name: user.name, email: user.username }
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 }, // 30 days
  pages: { signIn: "/login" },
  callbacks: {
    authorized({ auth }) {
      return !!auth?.user
    },
    jwt({ token, user }) {
      if (user) { token.userId = user.id }
      return token
    },
    session({ session, token }) {
      if (token.userId) {
        session.user.id = token.userId as string
      }
      return session
    },
  },
  trustHost: true,
})

// src/middleware.ts
export { auth as middleware } from "@/auth"
export const config = {
  matcher: ["/dashboard/:path*"],
}
```

### Pattern 3: Sheet Slide-Out for Listing Detail

**What:** Clicking a result card opens a shadcn/ui Sheet from the right showing full listing detail. The results list remains visible behind an overlay.

**When to use:** DASH-02, DASH-03, DASH-09.

**Example:**
```tsx
// src/components/search/listing-detail.tsx
"use client"
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ExternalLink, Mail, Phone, FileText } from "lucide-react"
import type { ListingDetail } from "@/types/listing"

interface Props {
  listing: ListingDetail | null
  open: boolean
  onClose: () => void
}

export function ListingDetailSheet({ listing, open, onClose }: Props) {
  if (!listing) return null

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className="w-[600px] sm:max-w-[600px] overflow-y-auto">
        <SheetHeader>
          <div className="flex items-center gap-2">
            <Badge variant={listing.status === "open" ? "default" : "secondary"}>
              {listing.status}
            </Badge>
          </div>
          <SheetTitle className="text-lg">{listing.title}</SheetTitle>
          <SheetDescription>{listing.source_portal_name}</SheetDescription>
        </SheetHeader>

        {/* Dates */}
        <div className="grid grid-cols-2 gap-4 py-4 border-b">
          <div>
            <p className="text-sm text-muted-foreground">Posted</p>
            <p>{listing.posting_date ? format(listing.posting_date) : "Not specified"}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Closing</p>
            <p>{listing.closing_date ? format(listing.closing_date) : "Not specified"}</p>
          </div>
        </div>

        {/* Description */}
        <div className="py-4 border-b">
          <h3 className="font-semibold mb-2">Description</h3>
          <p className="text-sm whitespace-pre-wrap">{listing.description || "Not specified"}</p>
        </div>

        {/* Documents */}
        {listing.documents && listing.documents.length > 0 && (
          <div className="py-4 border-b">
            <h3 className="font-semibold mb-2">Documents</h3>
            {listing.documents.map((doc, i) => (
              <a key={i} href={doc.url} target="_blank" rel="noopener noreferrer"
                 className="flex items-center gap-2 p-2 rounded hover:bg-muted">
                <FileText className="h-4 w-4" />
                <div>
                  <p className="text-sm font-medium">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">{doc.type || "Document"}</p>
                </div>
              </a>
            ))}
          </div>
        )}

        {/* Contact Card */}
        {listing.contact_info && (
          <div className="py-4 border-b">
            <h3 className="font-semibold mb-2">Contact</h3>
            <div className="space-y-2">
              {listing.contact_info.name && <p className="font-medium">{listing.contact_info.name}</p>}
              {listing.contact_info.email && (
                <a href={`mailto:${listing.contact_info.email}`} className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                  <Mail className="h-4 w-4" /> {listing.contact_info.email}
                </a>
              )}
              {listing.contact_info.phone && (
                <a href={`tel:${listing.contact_info.phone}`} className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                  <Phone className="h-4 w-4" /> {listing.contact_info.phone}
                </a>
              )}
            </div>
          </div>
        )}

        {/* Source Link */}
        <div className="py-4">
          <Button asChild className="w-full" size="lg">
            <a href={listing.source_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" /> View on Source Portal
            </a>
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

### Pattern 4: Server-Side Pagination via API

**What:** The search page uses server-side pagination. The FastAPI endpoint handles LIMIT/OFFSET. The frontend controls pagination state via nuqs and passes `page` + `page_size` to the API. TanStack Table manages display with `manualPagination: true`.

**When to use:** DASH-01 (paginated results).

**Key configuration:**
```typescript
const table = useReactTable({
  data: results,
  columns,
  getCoreRowModel: getCoreRowModel(),
  manualPagination: true,
  pageCount: totalPages,  // from API response
  state: {
    pagination: { pageIndex: params.page - 1, pageSize: params.page_size },
  },
  onPaginationChange: (updater) => {
    const next = typeof updater === "function"
      ? updater({ pageIndex: params.page - 1, pageSize: params.page_size })
      : updater
    setParams({ page: next.pageIndex + 1, page_size: next.pageSize })
  },
})
```

### Pattern 5: Data Fetching Architecture

**What:** The Next.js app fetches from the FastAPI API via HTTP. Server components and route handlers use the internal Docker network URL (`http://api:8000`). Client components fetch via the browser through nginx (`/api/...`).

**Why:** The existing nginx config proxies `/api/` to `http://api:8000/`. Client-side fetches go through this proxy naturally. Server-side fetches (Auth.js authorize callback, server components) need the internal Docker URL.

**Example:**
```typescript
// src/lib/api.ts
// Internal URL for server-side requests (Docker network)
const API_INTERNAL = process.env.API_INTERNAL_URL || "http://api:8000"
// Browser requests go through nginx proxy at /api/
const API_PUBLIC = "/api"

export function getApiUrl(server: boolean = false): string {
  return server ? API_INTERNAL : API_PUBLIC
}

export async function fetchListing(id: string): Promise<ListingDetail> {
  const res = await fetch(`${API_PUBLIC}/listings/${id}`)
  if (!res.ok) throw new Error("Failed to fetch listing")
  return res.json()
}
```

### Anti-Patterns to Avoid

- **Fetching from server components for the search page:** The search page must be a client component tree because filter state is interactive and URL-synced. Do NOT try to make it a server component with searchParams -- nuqs requires client-side hooks. Server components are fine for the layout shell, nav, and static content.
- **Storing search state in React state instead of URL:** All search/filter/sort/page state MUST be in the URL (DASH-08 requirement). Never use `useState` for filter values -- use `useQueryStates` from nuqs.
- **Using `getServerSideProps` or Pages Router patterns:** This is an App Router project. No `getServerSideProps`, no `pages/` directory.
- **Building auth from scratch with jose/JWT:** Auth.js v5 handles cookie management, CSRF protection, session rotation, and middleware integration. Rolling your own for "simplicity" creates security gaps.
- **Fetching API_INTERNAL_URL from client components:** The Docker-internal URL is not reachable from the browser. Client components must always fetch through `/api/` (nginx proxy).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL state sync | Custom useSearchParams parsing/serialization | nuqs `useQueryStates` | Handles batching, type safety, history mode, back/forward. Dozens of edge cases with arrays, nulls, defaults. |
| Authentication | Custom JWT + cookie management | Auth.js v5 Credentials provider | CSRF, cookie rotation, secure HttpOnly cookies, middleware integration, session callbacks. Security-critical. |
| Data table pagination | Custom pagination logic + page state | TanStack Table `manualPagination` | Handles pageCount calculation, getCanNextPage/Previous, pagination state. |
| Side panel / overlay | Custom portal + animation + focus trap | shadcn/ui Sheet (Radix Dialog) | Focus trapping, keyboard navigation, scroll lock, animation, accessibility. |
| Date formatting | Manual date string manipulation | date-fns `format`, `formatDistanceToNow` | Locale support, relative time ("3 days ago"), edge cases with timezones. |
| Form validation | Manual if/else checks | zod schemas | Type inference, composable, works with Auth.js, consistent error messages. |
| CSS utility merging | String concatenation of classnames | `cn()` from shadcn/ui (clsx + twMerge) | Properly merges conflicting Tailwind classes (e.g., `p-2` + `p-4` = `p-4`). |
| Password hashing | SHA256 or plaintext | bcryptjs with salt rounds | Bcrypt is intentionally slow, resistant to rainbow tables. Never store plaintext passwords even for 3 users. |

**Key insight:** This is a 3-user internal tool, but authentication and URL state management still have genuine complexity. The libraries are small (nuqs 6KB, Auth.js ~30KB) and eliminate real bug classes. The time saved vs hand-rolling is significant.

## Common Pitfalls

### Pitfall 1: Client/Server Component Boundary Confusion
**What goes wrong:** Putting `"use client"` on the layout breaks server-side auth checks. Or trying to use `useQueryStates` in a server component.
**Why it happens:** Next.js App Router requires clear thinking about which components are server vs client.
**How to avoid:** The root layout and dashboard layout are server components. They wrap client component children. The search page content (`page.tsx`) can export a client component. Auth checks happen in middleware (server) and the dashboard layout (server). Interactive components (search, filters, table, sheet) are all client components.
**Warning signs:** Hydration errors, "useState is not defined" errors in server components.

### Pitfall 2: nuqs NuqsAdapter Missing
**What goes wrong:** `useQueryState` throws "No NuqsAdapter found" error at runtime.
**Why it happens:** nuqs requires a provider component in the component tree.
**How to avoid:** Wrap the app in `NuqsAdapter` from `nuqs/adapters/next/app` in the root layout. Must be inside the `<body>` tag.
**Warning signs:** Runtime error on first page load, works in dev but crashes in production.

### Pitfall 3: Docker Internal vs External API URLs
**What goes wrong:** Server-side auth calls to FastAPI fail because they use `/api/...` which resolves to the Next.js container itself, not the FastAPI service.
**Why it happens:** Inside Docker, containers communicate via service names (e.g., `http://api:8000`). The browser uses the nginx proxy at `/api/`.
**How to avoid:** Use `API_INTERNAL_URL=http://api:8000` env var for server-side requests. Client-side requests always use relative `/api/` paths.
**Warning signs:** ECONNREFUSED in server logs, 404s from server-side fetches.

### Pitfall 4: Search Page Full Re-render on Every Keystroke
**What goes wrong:** Typing in the search box triggers a URL update + API fetch on every character.
**Why it happens:** nuqs syncs to URL on every state change by default.
**How to avoid:** Use `throttleMs` option in nuqs (e.g., 300ms) for the search input, or use a local state for the input value and sync to nuqs on submit/debounce.
**Warning signs:** Excessive API requests, laggy input, browser URL flickering.

### Pitfall 5: "New" Badge Stale After Dashboard Open
**What goes wrong:** User opens dashboard, `last_visited_at` updates immediately, and all "New" badges disappear before the user sees them.
**Why it happens:** Updating `last_visited_at` on page load before rendering results.
**How to avoid:** On dashboard load: (1) read current `last_visited_at`, (2) render results with "New" badges based on the OLD timestamp, (3) THEN update `last_visited_at` for next visit. The API should return the previous `last_visited_at` and then update it.
**Warning signs:** "New" badges never appear, or flash briefly then disappear.

### Pitfall 6: Next.js Standalone Mode Missing Static Files
**What goes wrong:** Production Docker build works but CSS/images are 404.
**Why it happens:** `output: "standalone"` does NOT copy the `public/` folder or `.next/static/` automatically. They must be manually copied in the Dockerfile.
**How to avoid:** In the Dockerfile runner stage, copy three things: `.next/standalone`, `.next/static`, and `public/`.
**Warning signs:** Broken styles in production, working in dev.

### Pitfall 7: Auth.js v5 Credentials Provider Returns Null Silently
**What goes wrong:** Login fails with no error message.
**Why it happens:** The `authorize` callback returns `null` for invalid credentials, and without custom error pages/handling, the user sees a generic redirect.
**How to avoid:** Use a server action for login that catches `CredentialsSignin` errors and returns a user-friendly message. The custom `/login` page handles display.
**Warning signs:** Login button does nothing, or redirects back to login with no feedback.

### Pitfall 8: CORS Issues Between Next.js and FastAPI
**What goes wrong:** Browser blocks API requests with CORS errors.
**Why it happens:** If Next.js tries to fetch directly from `api:8000` from the browser, or if nginx headers are misconfigured.
**How to avoid:** All browser requests go through nginx, which proxies both `/` (Next.js) and `/api/` (FastAPI) from the same origin. No CORS needed. Never expose FastAPI directly to the browser.
**Warning signs:** CORS preflight failures in browser console.

## Code Examples

### New FastAPI Endpoints Needed

```python
# api/routers/listings.py -- NEW FILE
"""Listing detail endpoint."""
from fastapi import APIRouter, HTTPException
from api.db import get_connection

router = APIRouter(tags=["listings"])

@router.get("/listings/{listing_id}")
def get_listing(listing_id: str):
    """Return full listing detail by ID."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT l.*, p.name as source_portal_name, p.url as portal_url
                FROM listings l
                JOIN portals p ON l.source_portal = p.id
                WHERE l.id = %s
            """, (listing_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Listing not found")
            # Convert UUID, datetime to strings for JSON serialization
            return dict(row)
    finally:
        conn.close()


# api/routers/portal_health.py -- NEW FILE
"""Scraper health endpoints."""
from fastapi import APIRouter
from api.db import get_connection

router = APIRouter(tags=["health"])

@router.get("/health/portals")
def get_portal_health():
    """Return scraper health status per portal with last 5 runs."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                WITH latest_runs AS (
                    SELECT sr.*,
                           ROW_NUMBER() OVER (PARTITION BY sr.portal_id ORDER BY sr.started_at DESC) as rn
                    FROM scrape_runs sr
                ),
                portal_stats AS (
                    SELECT portal_id,
                           COUNT(*) FILTER (WHERE rn <= 5 AND status = 'failed') as recent_failures,
                           COUNT(*) FILTER (WHERE rn <= 5) as recent_total,
                           MAX(completed_at) FILTER (WHERE status = 'completed') as last_success_at,
                           MAX(started_at) as last_run_at
                    FROM latest_runs
                    WHERE rn <= 5
                    GROUP BY portal_id
                )
                SELECT p.id, p.name, p.url, p.level, p.province, p.enabled,
                       ps.recent_failures, ps.recent_total,
                       ps.last_success_at, ps.last_run_at,
                       lr.status as last_status, lr.listings_found, lr.listings_new,
                       lr.listings_updated, lr.duration_seconds, lr.error_message,
                       (SELECT COUNT(*) FROM listings WHERE source_portal = p.id) as total_listings
                FROM portals p
                LEFT JOIN portal_stats ps ON ps.portal_id = p.id
                LEFT JOIN latest_runs lr ON lr.portal_id = p.id AND lr.rn = 1
                ORDER BY p.name
            """)
            return cur.fetchall()
    finally:
        conn.close()

@router.get("/health/freshness")
def get_data_freshness():
    """Return the most recent successful scrape completion time."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(completed_at) as last_updated
                FROM scrape_runs WHERE status = 'completed'
            """)
            row = cur.fetchone()
            return {"last_updated": row[0] if row else None}
    finally:
        conn.close()


# api/routers/users.py -- NEW FILE
"""User endpoints for auth support."""
from fastapi import APIRouter, HTTPException
from api.db import get_connection

router = APIRouter(tags=["users"])

@router.get("/auth/user")
def get_user_by_username(username: str):
    """Return user by username (for Auth.js authorize callback)."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, name, password_hash, last_visited_at FROM users WHERE username = %s",
                (username,),
            )
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return dict(user)
    finally:
        conn.close()

@router.get("/users/{user_id}/last-visit")
def get_last_visit(user_id: str):
    """Return user's last_visited_at timestamp."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT last_visited_at FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404)
            return {"last_visited_at": row[0]}
    finally:
        conn.close()

@router.put("/users/{user_id}/last-visit")
def update_last_visit(user_id: str):
    """Update user's last_visited_at to NOW(). Called on dashboard open."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_visited_at = NOW() WHERE id = %s RETURNING last_visited_at",
                (user_id,),
            )
            conn.commit()
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404)
            return {"last_visited_at": row[0]}
    finally:
        conn.close()
```

### Database Migration for Users Table

```sql
-- db/migrations/005_users.sql
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(100) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    password_hash   TEXT NOT NULL,
    last_visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed 3 BD team users with bcrypt-hashed passwords
-- Passwords should be generated with: node -e "require('bcryptjs').hash('password', 10).then(console.log)"
-- PLACEHOLDER: replace hashed passwords before deployment
INSERT INTO users (username, name, password_hash) VALUES
    ('user1', 'BD User 1', '$2a$10$PLACEHOLDER_HASH_1'),
    ('user2', 'BD User 2', '$2a$10$PLACEHOLDER_HASH_2'),
    ('user3', 'BD User 3', '$2a$10$PLACEHOLDER_HASH_3')
ON CONFLICT (username) DO NOTHING;
```

### NuqsAdapter Root Layout Setup

```tsx
// src/app/layout.tsx
import type { Metadata } from "next"
import { NuqsAdapter } from "nuqs/adapters/next/app"
import "@/app/globals.css"

export const metadata: Metadata = {
  title: "Procurement Intelligence Platform",
  description: "Search Canadian government procurement opportunities",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <NuqsAdapter>{children}</NuqsAdapter>
      </body>
    </html>
  )
}
```

### Next.js Standalone Dockerfile

```dockerfile
# web/Dockerfile
FROM node:20-alpine AS base

# --- Dependencies ---
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# --- Build ---
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Runner ---
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

### next.config.ts

```typescript
// web/next.config.ts
import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
  // No rewrites needed -- nginx handles /api/ proxying to FastAPI
  // Environment variables:
  //   API_INTERNAL_URL=http://api:8000  (for server-side fetches)
  //   NEXTAUTH_SECRET=...               (for Auth.js)
  //   NEXTAUTH_URL=https://procurement.eliastools.com
}

export default nextConfig
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pages Router + getServerSideProps | App Router + Server/Client Components | Next.js 13+ (stable 14+) | Data fetching is per-component, not per-page. Layout nesting. |
| next-auth v4 | Auth.js v5 (next-auth@beta) | 2024-2025 | Single `auth()` function works everywhere. Edge-compatible. `authorized` callback in middleware. |
| Manual URL params parsing | nuqs v2 | 2024-2025 | Type-safe URL state with batching, throttling, history modes. |
| tailwind.config.js | Tailwind CSS v4 (CSS-native config) | 2025 | No config file needed; uses CSS `@theme` directive. shadcn/ui supports both v3 and v4. |
| next-auth Credentials + adapter | Auth.js v5 Credentials + JWT (no adapter) | 2024 | Credentials provider works best with JWT strategy (no database adapter needed for sessions). |
| shadcn/ui separate Radix packages | shadcn/ui unified `radix-ui` import | 2026 (new-york style) | Cleaner package.json, fewer imports. |

**Deprecated/outdated:**
- `getServerSideProps` / `getStaticProps`: Only work in Pages Router. Use Server Components in App Router.
- `next-auth` v4 `unstable_getServerSession`: Replaced by `auth()` in v5.
- `useRouter().query` (Pages Router): Use `useSearchParams()` or nuqs in App Router.
- `tailwind.config.ts` with plugins: Tailwind v4 uses `@theme` in CSS. shadcn/ui init handles this automatically.

## Open Questions

1. **Next.js 15 vs 16 decision**
   - What we know: Next.js 16 is available (released Dec 2025) with `proxy.ts` replacing `middleware.ts`. Next.js 15 is mature and battle-tested.
   - What's unclear: Whether Auth.js v5 fully supports Next.js 16's proxy.ts pattern yet.
   - Recommendation: Use Next.js 15. It is stable, all libraries support it, and Auth.js middleware works perfectly. Upgrade to 16 later if needed. The middleware rename is the main breaking change.

2. **Auth.js v5 beta stability**
   - What we know: Auth.js v5 has been in beta since 2024. It is widely used in production by many companies. The API is stable.
   - What's unclear: When the final stable release will ship.
   - Recommendation: Use `next-auth@beta` (v5). The beta label is misleading -- the library is production-ready and the standard for Next.js App Router auth. Pinning to a specific beta version (e.g., `5.0.0-beta.25`) in package.json is prudent.

3. **shadcn/ui Tailwind v4 vs v3**
   - What we know: shadcn/ui supports both. Tailwind v4 ships with `create-next-app` in Next.js 15.
   - Recommendation: Use Tailwind v4 (default). shadcn/ui `init` auto-detects and configures correctly.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright (E2E) + Vitest (unit/component) + pytest (API endpoints) |
| Config file | `web/vitest.config.ts` (Wave 0), `web/playwright.config.ts` (Wave 0), `api/tests/conftest.py` (exists) |
| Quick run command | `cd web && npx vitest run --reporter=verbose` |
| Full suite command | `cd web && npx vitest run && npx playwright test && cd ../api && python -m pytest tests/ -x` |
| Estimated runtime | ~15 seconds (vitest) + ~30 seconds (playwright) + ~5 seconds (pytest) |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Paginated listing results in searchable table | E2E | `npx playwright test search.spec.ts` | No -- Wave 0 |
| DASH-02 | Click listing opens full detail | E2E | `npx playwright test listing-detail.spec.ts` | No -- Wave 0 |
| DASH-03 | Detail includes source portal link | E2E | `npx playwright test listing-detail.spec.ts` | No -- Wave 0 |
| DASH-04 | Login with username/password | E2E + unit | `npx playwright test auth.spec.ts` | No -- Wave 0 |
| DASH-05 | Data freshness indicator | unit | `npx vitest run freshness` | No -- Wave 0 |
| DASH-06 | "New" badge on recent listings | unit + E2E | `npx vitest run new-badge && npx playwright test search.spec.ts` | No -- Wave 0 |
| DASH-07 | Scraper health page per-portal | E2E | `npx playwright test health.spec.ts` | No -- Wave 0 |
| DASH-08 | Filter state synced to URL | E2E | `npx playwright test url-state.spec.ts` | No -- Wave 0 |
| DASH-09 | Document attachments and contact info in detail | E2E | `npx playwright test listing-detail.spec.ts` | No -- Wave 0 |
| -- | Listing detail API endpoint | unit (pytest) | `python -m pytest api/tests/test_listings.py -x` | No -- Wave 0 |
| -- | Portal health API endpoint | unit (pytest) | `python -m pytest api/tests/test_portal_health.py -x` | No -- Wave 0 |
| -- | User auth API endpoint | unit (pytest) | `python -m pytest api/tests/test_users.py -x` | No -- Wave 0 |

### Nyquist Sampling Rate

- **Minimum sample interval:** After every committed task, run: `cd web && npx vitest run --reporter=verbose`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green (vitest + playwright + pytest) before `/gsd:verify-work`
- **Estimated feedback latency per task:** ~15 seconds (vitest unit tests)

### Wave 0 Gaps (must be created before implementation)

- [ ] `web/vitest.config.ts` -- Vitest configuration for Next.js (with next/jest or vitest-next)
- [ ] `web/playwright.config.ts` -- Playwright configuration pointing at localhost:3000
- [ ] `web/tests/e2e/auth.spec.ts` -- Login flow E2E test scaffold
- [ ] `web/tests/e2e/search.spec.ts` -- Search and pagination E2E test scaffold
- [ ] `web/tests/e2e/listing-detail.spec.ts` -- Sheet slide-out detail E2E test scaffold
- [ ] `web/tests/e2e/health.spec.ts` -- Health page E2E test scaffold
- [ ] `web/tests/e2e/url-state.spec.ts` -- URL state sync E2E test scaffold
- [ ] `web/src/__tests__/` -- Unit test directory for components and hooks
- [ ] `api/tests/test_listings.py` -- Listing detail endpoint unit tests
- [ ] `api/tests/test_portal_health.py` -- Portal health endpoint unit tests
- [ ] `api/tests/test_users.py` -- User auth endpoint unit tests
- [ ] Framework installs: `npm install -D vitest @vitejs/plugin-react @playwright/test`

## Sources

### Primary (HIGH confidence)
- [Auth.js v5 Next.js Reference](https://authjs.dev/reference/nextjs) -- Configuration, exports, middleware, callbacks, session strategy
- [shadcn/ui Data Table Guide](https://ui.shadcn.com/docs/components/radix/data-table) -- TanStack Table integration, pagination, filtering patterns
- [shadcn/ui Sheet Component](https://ui.shadcn.com/docs/components/radix/sheet) -- Side panel API, subcomponents, side prop
- [nuqs GitHub](https://github.com/47ng/nuqs) -- NuqsAdapter setup, useQueryState/useQueryStates examples, parser list
- [nuqs Built-in Parsers](https://nuqs.dev/docs/parsers/built-in) -- Full parser list: parseAsString, parseAsInteger, parseAsFloat, parseAsBoolean, parseAsTimestamp, parseAsIsoDateTime, parseAsArrayOf, parseAsStringEnum, parseAsStringLiteral
- [nuqs Batching Docs](https://nuqs.dev/docs/batching) -- useQueryStates API, batching behavior, urlKeys remapping
- [TanStack Table Pagination API](https://tanstack.com/table/v8/docs/api/features/pagination) -- manualPagination, pageCount, rowCount, onPaginationChange
- [Next.js Official Docker Example](https://github.com/vercel/next.js/blob/canary/examples/with-docker/Dockerfile) -- Multi-stage standalone Dockerfile
- [Next.js Server/Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components) -- RSC patterns, client boundary rules
- [shadcn/ui Installation for Next.js](https://ui.shadcn.com/docs/installation/next) -- Init command, component addition

### Secondary (MEDIUM confidence)
- [Auth.js Protecting Routes](https://authjs.dev/getting-started/session-management/protecting) -- Middleware auth patterns verified against official docs
- [Next.js Conf 2025 nuqs talk](https://nextjs.org/conf/session/type-safe-url-state-in-nextjs-with-nuqs) -- nuqs adoption by Vercel, Sentry, Supabase
- [shadcn/ui Changelog](https://ui.shadcn.com/docs/changelog) -- Tailwind v4 support, unified radix-ui imports (2026)
- Various Medium/DEV Community guides for Auth.js v5 Credentials pattern -- cross-verified with official docs

### Tertiary (LOW confidence)
- Next.js 16 release details -- confirmed it exists but not using it; sticking with 15

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries verified via official docs and npm. Versions confirmed.
- Architecture: HIGH -- Patterns sourced from official Next.js, shadcn/ui, and nuqs documentation. Codebase structure aligns with existing project conventions.
- Pitfalls: HIGH -- Based on documented gotchas from official sources (Auth.js migration guide, nuqs adapter requirement, Next.js standalone docs) and known Docker networking patterns.
- FastAPI additions: HIGH -- Straightforward SQL queries against existing schema. No new Python dependencies needed.
- Validation: MEDIUM -- Test framework recommendations are standard but Playwright E2E tests will depend on having a running Docker environment.

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days -- stable ecosystem, no major releases expected)
