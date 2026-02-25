---
phase: 4-web-application
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - db/migrations/005_users.sql
  - api/routers/listings.py
  - api/routers/portal_health.py
  - api/routers/users.py
  - api/main.py
  - api/requirements.txt
  - web/package.json
  - web/next.config.ts
  - web/tsconfig.json
  - web/src/app/layout.tsx
  - web/src/app/page.tsx
  - web/src/app/login/page.tsx
  - web/src/app/api/auth/[...nextauth]/route.ts
  - web/src/app/dashboard/layout.tsx
  - web/src/app/dashboard/page.tsx
  - web/src/auth.ts
  - web/src/middleware.ts
  - web/src/components/login-form.tsx
  - web/src/components/layout/nav.tsx
  - web/src/lib/api.ts
  - web/src/lib/utils.ts
  - web/src/types/search.ts
  - web/src/types/listing.ts
  - web/src/types/health.ts
  - web/components.json
autonomous: true
requirements:
  - DASH-04

must_haves:
  truths:
    - "User can log in with username and password and reach a protected dashboard"
    - "Invalid credentials show an error message on the login page"
    - "Unauthenticated users are redirected to /login when visiting /dashboard"
    - "GET /api/listings/{id} returns full listing detail with all fields"
    - "GET /api/health/portals returns per-portal scraper health data"
    - "GET /api/health/freshness returns most recent successful scrape timestamp"
    - "GET /api/auth/user?username=X returns user record for Auth.js authorize"
    - "GET and PUT /api/users/{id}/last-visit read and update last_visited_at"
  artifacts:
    - path: "db/migrations/005_users.sql"
      provides: "Users table with 3 seeded accounts"
      contains: "CREATE TABLE"
    - path: "api/routers/listings.py"
      provides: "Listing detail endpoint"
      exports: ["router"]
    - path: "api/routers/portal_health.py"
      provides: "Portal health and freshness endpoints"
      exports: ["router"]
    - path: "api/routers/users.py"
      provides: "User auth and last-visit endpoints"
      exports: ["router"]
    - path: "web/src/auth.ts"
      provides: "Auth.js v5 configuration with Credentials provider"
      exports: ["handlers", "auth", "signIn", "signOut"]
    - path: "web/src/middleware.ts"
      provides: "Auth middleware protecting /dashboard/*"
      min_lines: 3
    - path: "web/src/app/login/page.tsx"
      provides: "Login page with form"
      min_lines: 10
    - path: "web/src/app/dashboard/layout.tsx"
      provides: "Dashboard shell with nav"
      min_lines: 15
  key_links:
    - from: "web/src/auth.ts"
      to: "/api/auth/user"
      via: "fetch in authorize callback"
      pattern: "API_INTERNAL_URL.*auth/user"
    - from: "web/src/middleware.ts"
      to: "web/src/auth.ts"
      via: "export { auth as middleware }"
      pattern: "auth.*middleware"
    - from: "api/main.py"
      to: "api/routers/listings.py"
      via: "app.include_router"
      pattern: "include_router.*listings"
---

<objective>
Create all new FastAPI endpoints (listing detail, portal health, freshness, user auth, last-visit tracking), the users DB migration with 3 seed accounts, and a complete Next.js 15 project scaffold with Auth.js v5 authentication, login page, and protected dashboard shell.

Purpose: Everything else in Phase 4 depends on the API endpoints existing and the Next.js project being scaffolded with auth in place. This plan delivers a working login-to-dashboard flow and testable API endpoints.

Output: User can log in at /login, reach a protected /dashboard page with navigation shell, and all 6 new FastAPI endpoints return correct data.
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
@api/main.py
@api/db.py
@api/config.py
@api/routers/health.py
@api/routers/search.py
@api/models/response.py
@api/models/request.py
@db/migrations/001_initial_schema.sql
@docker-compose.yml
@nginx/nginx.conf
@web/Dockerfile
@web/server.js
</context>

<tasks>

<task type="auto">
  <name>Task 1: FastAPI endpoints + users migration</name>
  <files>
    db/migrations/005_users.sql
    api/routers/listings.py
    api/routers/portal_health.py
    api/routers/users.py
    api/main.py
  </files>
  <action>
    1. Create `db/migrations/005_users.sql`:
       - CREATE TABLE users (id UUID PK DEFAULT gen_random_uuid(), username VARCHAR(100) NOT NULL UNIQUE, name VARCHAR(255) NOT NULL, password_hash TEXT NOT NULL, last_visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())
       - Generate 3 bcrypt password hashes using Node.js: `node -e "require('bcryptjs').hash('changeme1', 10).then(h => console.log(h))"` (run 3 times with passwords changeme1, changeme2, changeme3)
       - INSERT 3 seed users: (user1, 'BD User 1', hash1), (user2, 'BD User 2', hash2), (user3, 'BD User 3', hash3) with ON CONFLICT (username) DO NOTHING

    2. Create `api/routers/listings.py`:
       - GET /listings/{listing_id} endpoint
       - Query: SELECT l.*, p.name as source_portal_name, p.url as portal_url FROM listings l JOIN portals p ON l.source_portal = p.id WHERE l.id = %s
       - Use RealDictCursor for dict results
       - Return 404 HTTPException if not found
       - Handle UUID, datetime, Decimal serialization (cast id to str, use json_serial helper or let FastAPI handle via response_model)
       - Import psycopg2.extras at top of file

    3. Create `api/routers/portal_health.py`:
       - GET /health/portals: Per-portal health with last 5 runs aggregation
         - CTE: latest_runs with ROW_NUMBER() OVER (PARTITION BY portal_id ORDER BY started_at DESC) as rn
         - CTE: portal_stats aggregating recent_failures (COUNT FILTER WHERE rn <= 5 AND status='failed'), recent_total, last_success_at, last_run_at
         - Final query: JOIN portals with portal_stats and latest_runs (rn=1), include total_listings subquery count
         - ORDER BY p.name
       - GET /health/freshness: SELECT MAX(completed_at) as last_updated FROM scrape_runs WHERE status = 'completed'
       - Both use RealDictCursor, import psycopg2.extras

    4. Create `api/routers/users.py`:
       - GET /auth/user?username=X: Lookup user by username, return id, username, name, password_hash, last_visited_at. 404 if not found. Use RealDictCursor.
       - GET /users/{user_id}/last-visit: Return last_visited_at for user. 404 if not found.
       - PUT /users/{user_id}/last-visit: UPDATE users SET last_visited_at = NOW() WHERE id = %s RETURNING last_visited_at. Commit. 404 if not found.
       - All use RealDictCursor and import psycopg2.extras

    5. Update `api/main.py`:
       - Add imports: from api.routers import listings, portal_health, users
       - Add: app.include_router(listings.router), app.include_router(portal_health.router), app.include_router(users.router)
       - Keep existing health and search router registrations

    Note: Do NOT add bcrypt to api/requirements.txt. Password verification happens in the Next.js layer using bcryptjs. The FastAPI /auth/user endpoint returns the hash for Auth.js to compare client-side.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -c "from api.routers import listings, portal_health, users; print('All routers import OK')" && python -c "from api.main import app; routes = [r.path for r in app.routes]; assert '/listings/{listing_id}' in routes; assert '/health/portals' in routes; assert '/health/freshness' in routes; assert '/auth/user' in routes; print('All routes registered:', routes)"</automated>
    <manual>Verify 005_users.sql has valid SQL and 3 INSERT statements with bcrypt hashes</manual>
  </verify>
  <done>
    - 005_users.sql creates users table with 3 seeded accounts (bcrypt-hashed passwords)
    - GET /listings/{id} returns full listing detail with portal name and URL
    - GET /health/portals returns per-portal health aggregation
    - GET /health/freshness returns last successful scrape timestamp
    - GET /auth/user?username=X returns user record
    - GET and PUT /users/{id}/last-visit read and update last_visited_at
    - All 4 new routers registered in api/main.py
  </done>
</task>

<task type="auto">
  <name>Task 2: Next.js scaffold + Auth.js + login page + dashboard shell</name>
  <files>
    web/package.json
    web/next.config.ts
    web/tsconfig.json
    web/src/app/layout.tsx
    web/src/app/globals.css
    web/src/app/page.tsx
    web/src/app/login/page.tsx
    web/src/app/api/auth/[...nextauth]/route.ts
    web/src/app/dashboard/layout.tsx
    web/src/app/dashboard/page.tsx
    web/src/auth.ts
    web/src/middleware.ts
    web/src/components/login-form.tsx
    web/src/components/layout/nav.tsx
    web/src/lib/api.ts
    web/src/lib/utils.ts
    web/src/lib/format.ts
    web/src/types/search.ts
    web/src/types/listing.ts
    web/src/types/health.ts
    web/components.json
  </files>
  <action>
    1. Delete all existing files in web/ (server.js, package.json, Dockerfile are the Express stub — completely replaced).

    2. Scaffold Next.js project in web/:
       ```bash
       cd web && npx create-next-app@latest . --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --yes
       ```
       If create-next-app fails because directory is not empty, remove the old files first.

    3. Install dependencies:
       ```bash
       cd web && npm install next-auth@beta nuqs @tanstack/react-table bcryptjs date-fns zod lucide-react
       npm install -D @types/bcryptjs
       ```

    4. Initialize shadcn/ui:
       ```bash
       cd web && npx shadcn@latest init --defaults --yes
       ```
       Then add components needed across the app:
       ```bash
       npx shadcn@latest add button input badge card sheet table select skeleton separator scroll-area tooltip dropdown-menu label
       ```

    5. Create `web/next.config.ts`:
       ```typescript
       import type { NextConfig } from "next"
       const nextConfig: NextConfig = {
         output: "standalone",
       }
       export default nextConfig
       ```

    6. Create `web/src/lib/api.ts`:
       - Export API_INTERNAL_URL = process.env.API_INTERNAL_URL || "http://api:8000"
       - Export API_PUBLIC = "/api"
       - Export getApiUrl(server: boolean): string — returns internal or public URL
       - Export async fetchApi<T>(path: string, options?: RequestInit & { server?: boolean }): Promise<T> — generic fetch helper that prepends correct base URL, parses JSON, throws on non-ok response

    7. Create `web/src/lib/format.ts`:
       - Export formatDate(date: string | Date | null | undefined): string — returns formatted date or "Not specified"
       - Export formatCurrency(min?: number | null, max?: number | null): string — returns "$X - $Y" or "$X+" or "Value not disclosed"
       - Export formatRelativeTime(date: string | Date): string — uses date-fns formatDistanceToNow with addSuffix: true
       - All functions handle null/undefined gracefully per CONTEXT.md locked decision: show "Not specified" / "Value not disclosed", never blank

    8. Create TypeScript types in web/src/types/:
       - `search.ts`: ListingResult (matching API response model: id, title, source_portal_name, closing_date, province, value_min, value_max, snippet, posting_date), FacetValue (value, count), FacetCounts (provinces, portals), SearchResponse (results, total_count, page, page_size, total_pages, facets)
       - `listing.ts`: ListingDetail (all fields from listings table + source_portal_name + portal_url: id, title, description, status, posting_date, closing_date, amended_date, province, raw_location, classification_codes, value_min, value_max, contact_info: ContactInfo | null, documents: Document[], source_url, source_portal_name), ContactInfo (name?, email?, phone?, title?), Document (name, url, type?, date?)
       - `health.ts`: PortalHealth (id, name, url, level, province, enabled, recent_failures, recent_total, last_success_at, last_run_at, last_status, listings_found, listings_new, listings_updated, duration_seconds, error_message, total_listings), FreshnessData (last_updated: string | null)

    9. Create `web/src/auth.ts` — Auth.js v5 configuration:
       - Import NextAuth from "next-auth", Credentials from "next-auth/providers/credentials", compare from "bcryptjs", z from "zod"
       - getUser function: fetch from `${API_INTERNAL_URL}/auth/user?username=${encodeURIComponent(username)}` — return null if not ok, return parsed JSON otherwise
       - Credentials provider with username/password fields
       - authorize: validate with zod, getUser, compare password with bcryptjs, return { id: user.id, name: user.name, email: user.username } or null
       - session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 } (30 days)
       - pages: { signIn: "/login" }
       - callbacks: authorized({ auth }) returns !!auth?.user; jwt({ token, user }) adds userId; session({ session, token }) adds user.id
       - trustHost: true
       - Export { handlers, auth, signIn, signOut }
       - IMPORTANT: Import API_INTERNAL_URL from lib/api for the internal Docker URL

    10. Create `web/src/app/api/auth/[...nextauth]/route.ts`:
        - Import { handlers } from "@/auth"
        - Export { handlers.GET as GET, handlers.POST as POST }

    11. Create `web/src/middleware.ts`:
        - Export { auth as middleware } from "@/auth"
        - Export config = { matcher: ["/dashboard/:path*"] }

    12. Update `web/src/app/layout.tsx`:
        - Import NuqsAdapter from "nuqs/adapters/next/app"
        - Import globals.css
        - Metadata: title "Procurement Intelligence Platform", description "Search Canadian government procurement opportunities"
        - Wrap children in NuqsAdapter inside body tag
        - Use Inter font from next/font/google

    13. Create `web/src/app/page.tsx`:
        - Redirect to /dashboard using next/navigation redirect()
        - This is a server component

    14. Create `web/src/components/login-form.tsx`:
        - "use client" component
        - Form with username and password inputs (shadcn/ui Input + Label)
        - Submit handler calls signIn("credentials", { username, password, redirect: false })
        - Handle CredentialsSignin error: show "Invalid username or password" error message
        - On success: router.push("/dashboard")
        - Loading state on submit button
        - Styled with Tailwind: centered card layout, max-w-sm

    15. Create `web/src/app/login/page.tsx`:
        - Server component that renders the LoginForm client component
        - Centered layout with app title

    16. Create `web/src/components/layout/nav.tsx`:
        - "use client" component (needs signOut)
        - Top navigation bar with:
          - App title "Procurement Intelligence" on the left
          - Nav links: "Search" (/dashboard), "Scraper Health" (/dashboard/health)
          - User menu on the right with sign out button
        - Use shadcn/ui Button, lucide-react icons (Search, Activity, LogOut)
        - Active link highlighting based on pathname (usePathname)

    17. Create `web/src/app/dashboard/layout.tsx`:
        - Server component (auth check happens via middleware, no need to duplicate)
        - Renders Nav component + children in a flex column layout
        - Full height layout: nav at top, content area fills remaining space

    18. Create `web/src/app/dashboard/page.tsx`:
        - Placeholder: "Search page coming in Plan 4-02"
        - Simple centered text so the dashboard shell is visible and testable

    All components use shadcn/ui styling conventions. Import cn() from @/lib/utils (created by shadcn init).
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/web && npm run build 2>&1 | tail -20</automated>
    <manual>Verify the build succeeds without errors. Check that src/auth.ts, src/middleware.ts, and all page files exist.</manual>
  </verify>
  <done>
    - Next.js 15 project scaffolded with App Router, TypeScript, Tailwind CSS, shadcn/ui
    - All dependencies installed (next-auth@beta, nuqs, @tanstack/react-table, bcryptjs, date-fns, zod, lucide-react)
    - Auth.js v5 configured with Credentials provider, JWT sessions, 30-day maxAge
    - Middleware protects /dashboard/* routes
    - Login page at /login with username/password form and error handling
    - Dashboard shell at /dashboard with top nav (Search, Scraper Health, Sign Out)
    - NuqsAdapter wraps app in root layout
    - TypeScript types defined for search, listing, and health responses
    - API helper (lib/api.ts) handles internal vs public URL routing
    - Format helpers handle null values with "Not specified" / "Value not disclosed"
    - `npm run build` succeeds
  </done>
</task>

</tasks>

<verification>
1. All 4 new FastAPI routers import without errors
2. All 6 new routes registered in api/main.py
3. 005_users.sql contains valid CREATE TABLE and INSERT statements with bcrypt hashes
4. `cd web && npm run build` succeeds without errors
5. Auth.ts exports handlers, auth, signIn, signOut
6. Middleware.ts exports auth as middleware with /dashboard matcher
7. All TypeScript types match the API response models from Phase 3
</verification>

<success_criteria>
- FastAPI endpoints for listing detail, portal health, freshness, user auth, and last-visit are registered and importable
- Users migration creates table with 3 seeded accounts
- Next.js project builds successfully with all dependencies
- Auth.js v5 configured with Credentials provider and JWT sessions
- Login page, dashboard shell with nav, and auth middleware all exist
- TypeScript types, API helpers, and format utilities are in place
</success_criteria>

<output>
After completion, create `.planning/phases/4/4-01-SUMMARY.md`
</output>
