---
phase: 4-web-application
plan: 04
type: execute
wave: 2
depends_on: ["4-01"]
files_modified:
  - web/src/app/dashboard/health/page.tsx
  - web/src/components/health/portal-table.tsx
  - web/src/components/health/status-badge.tsx
  - web/src/hooks/use-portal-health.ts
  - web/Dockerfile
  - docker-compose.yml
autonomous: true
requirements:
  - DASH-07

must_haves:
  truths:
    - "User can navigate to /dashboard/health from the top nav"
    - "Health page shows a table of all portals with last-run date, success/fail status, listing count"
    - "Each portal row shows failure count ('Failed X of last Y runs')"
    - "3 consecutive failures show amber/warning status"
    - "7+ days since last successful scrape shows red/error status"
    - "Health page is accessible by all users (not admin-only)"
    - "Health page is purely informational (no action buttons)"
    - "Full Docker stack (db, api, web, nginx) starts and serves the Next.js app"
    - "Next.js app is reachable through nginx at /"
    - "API is reachable through nginx at /api/"
  artifacts:
    - path: "web/src/app/dashboard/health/page.tsx"
      provides: "Scraper health page"
      min_lines: 15
    - path: "web/src/components/health/portal-table.tsx"
      provides: "Portal health table with all columns"
      min_lines: 60
    - path: "web/src/components/health/status-badge.tsx"
      provides: "Color-coded status badge with staleness logic"
      min_lines: 20
    - path: "web/Dockerfile"
      provides: "Multi-stage standalone Docker build"
      contains: "standalone"
    - path: "docker-compose.yml"
      provides: "Updated web service for Next.js"
      contains: "API_INTERNAL_URL"
  key_links:
    - from: "web/src/hooks/use-portal-health.ts"
      to: "/api/health/portals"
      via: "fetch portal health data"
      pattern: "health/portals"
    - from: "web/src/components/health/status-badge.tsx"
      to: "staleness thresholds"
      via: "conditional rendering based on failures and days stale"
      pattern: "consecutive.*fail|days.*stale"
    - from: "docker-compose.yml"
      to: "web/Dockerfile"
      via: "build context for web service"
      pattern: "build.*web"
---

<objective>
Build the scraper health page with per-portal status table, staleness indicators, and failure counts. Update the web Dockerfile for Next.js standalone mode and verify Docker Compose integration with all services.

Purpose: The health page gives the BD team visibility into scraper reliability so they know which portals are current. Docker integration is the final step to make the full stack deployable.

Output: Health page at /dashboard/health shows per-portal status. Full stack runs in Docker Compose with Next.js replacing the Express stub.
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
@web/src/types/health.ts
@web/src/lib/api.ts
@web/src/lib/format.ts
@web/src/components/layout/nav.tsx
@docker-compose.yml
@nginx/nginx.conf
</context>

<tasks>

<task type="auto">
  <name>Task 1: Scraper health page with portal table, status badges, and staleness indicators</name>
  <files>
    web/src/hooks/use-portal-health.ts
    web/src/components/health/status-badge.tsx
    web/src/components/health/portal-table.tsx
    web/src/app/dashboard/health/page.tsx
  </files>
  <action>
    1. Create `web/src/hooks/use-portal-health.ts`:
       - "use client"
       - Export usePortalHealth() hook
       - Fetch from `/api/health/portals` on mount
       - Return { portals: PortalHealth[], loading: boolean, error: string | null }
       - Auto-refresh every 60 seconds (setInterval with cleanup)
       - PortalHealth type imported from types/health.ts

    2. Create `web/src/components/health/status-badge.tsx`:
       - "use client" component
       - Export StatusBadge component
       - Props: lastStatus (string | null — completed/failed/running), recentFailures (number), recentTotal (number), lastSuccessAt (string | null)
       - LOCKED DECISION — Staleness thresholds:
         a. HEALTHY (green): Last run succeeded AND fewer than 3 consecutive recent failures AND last success within 7 days
         b. WARNING/AMBER: 3+ consecutive failures in last 5 runs (recent_failures >= 3)
         c. ERROR/RED: 7+ days since last successful scrape (calculate days between now and lastSuccessAt)
         d. UNKNOWN (gray): No runs recorded (lastStatus is null)
         e. RUNNING (blue): lastStatus is "running"
       - Render shadcn Badge with appropriate variant and color
       - Show text: "Healthy", "Warning", "Stale", "No data", "Running"
       - Also export a helper function getPortalStatus(portal: PortalHealth) that returns the status category — reusable for sorting

    3. Create `web/src/components/health/portal-table.tsx`:
       - "use client" component
       - Props: portals (PortalHealth[]), loading (boolean)
       - Render a table (shadcn/ui Table components: Table, TableHeader, TableRow, TableHead, TableBody, TableCell)
       - Columns:
         a. Status: StatusBadge component
         b. Portal Name: portal.name (link to portal.url in new tab)
         c. Level: federal/provincial/municipal badge
         d. Province: portal.province or "-"
         e. Last Run: formatDate(portal.last_run_at) or "Never"
         f. Last Status: portal.last_status (completed/failed) with icon
         g. Listings: portal.total_listings count
         h. Recent: "Failed X of Y runs" (portal.recent_failures of portal.recent_total)
         i. Duration: portal.duration_seconds formatted as "Xs" or "-"
         j. Error: portal.error_message truncated to ~50 chars with tooltip for full text (shadcn Tooltip)
       - LOCKED DECISION: Failure counts visible: "Failed 3 of last 5 runs"
       - LOCKED DECISION: Purely informational — NO action buttons (no retry, disable, re-enable)
       - Default sort: status badges first (error > warning > healthy), then by name
       - Loading state: skeleton rows
       - Summary row or header: "X portals total, Y healthy, Z warnings, W errors"

    4. Create `web/src/app/dashboard/health/page.tsx`:
       - "use client" (or client component wrapper)
       - Call usePortalHealth() hook
       - Page title: "Scraper Health"
       - Render PortalTable with portals and loading from hook
       - LOCKED DECISION: Accessible by all users (already protected by /dashboard middleware, no additional auth check needed)
       - Simple page layout: heading + table, full width
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/web && npx tsc --noEmit --pretty 2>&1 | tail -20</automated>
    <manual>Verify status-badge.tsx implements all 3 staleness thresholds (healthy, 3 consecutive failures = amber, 7+ days stale = red)</manual>
  </verify>
  <done>
    - Health page renders at /dashboard/health
    - Portal table shows all portals with status, last run, listings count, failure rate
    - StatusBadge implements locked staleness thresholds: 3 failures = amber, 7+ days = red
    - Failure counts shown as "Failed X of Y runs"
    - No action buttons (purely informational per locked decision)
    - Auto-refreshes every 60 seconds
    - TypeScript compiles without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Docker integration — Next.js standalone Dockerfile and docker-compose update</name>
  <files>
    web/Dockerfile
    docker-compose.yml
  </files>
  <action>
    1. Replace `web/Dockerfile` with multi-stage standalone build:
       ```dockerfile
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
       CRITICAL (Pitfall 6 from research): Copy THREE things to runner stage:
       - .next/standalone (the standalone server)
       - .next/static (CSS, JS chunks)
       - public/ (static assets)

    2. Update `docker-compose.yml` web service:
       - Keep build: ./web
       - Add environment variables:
         - API_INTERNAL_URL=http://api:8000 (Docker internal URL for server-side fetches)
         - NEXTAUTH_SECRET=${NEXTAUTH_SECRET} (from .env)
         - NEXTAUTH_URL=https://procurement.eliastools.com (production URL)
       - Add depends_on: api (web needs API service for auth callbacks)
       - Keep depends_on: db (for any direct DB needs, though web uses API)
       - Keep expose: "3000", networks: internal, restart: unless-stopped
       - Remove the old env_file: .env if it's insufficient (Next.js needs specific env vars, not the full .env which has Python-specific vars). Actually keep env_file: .env since it already has NEXTAUTH_SECRET. Add environment: section for additional vars that override or supplement .env:
         ```yaml
         web:
           build: ./web
           restart: unless-stopped
           env_file: .env
           environment:
             - API_INTERNAL_URL=http://api:8000
             - NEXTAUTH_URL=https://procurement.eliastools.com
           depends_on:
             db:
               condition: service_healthy
             api:
               condition: service_started
           expose:
             - "3000"
           networks:
             - internal
         ```

    3. Verify the full docker-compose.yml is valid:
       - All 5 services defined: db, scraper, api, web, nginx
       - web depends on db (healthy) and api (started)
       - nginx depends on web and api
       - No circular dependencies
       - Volumes and networks preserved
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && docker compose config --quiet 2>&1 && echo "Docker Compose config valid"</automated>
    <manual>Verify Dockerfile has 3 stages (deps, builder, runner) and copies .next/standalone, .next/static, and public/ to runner</manual>
  </verify>
  <done>
    - web/Dockerfile is a multi-stage standalone build (deps -> builder -> runner)
    - Runner stage copies standalone + static + public (no missing static files)
    - docker-compose.yml has API_INTERNAL_URL and NEXTAUTH vars for web service
    - web service depends on db and api
    - `docker compose config` validates without errors
    - Full stack (db, scraper, api, web, nginx) is deployable via docker compose up
  </done>
</task>

</tasks>

<verification>
1. `cd web && npx tsc --noEmit` passes (TypeScript compilation)
2. Health page components compile: portal-table.tsx, status-badge.tsx, health/page.tsx
3. StatusBadge implements correct staleness thresholds (3 consecutive = amber, 7+ days = red)
4. No action buttons in health table (purely informational)
5. web/Dockerfile has 3 stages and copies standalone + static + public
6. `docker compose config` validates successfully
7. API_INTERNAL_URL=http://api:8000 is set in docker-compose web environment
</verification>

<success_criteria>
- Scraper health page accessible at /dashboard/health from top nav (DASH-07)
- Per-portal table shows last-run date, success/fail status, listing count
- Staleness indicators: 3 consecutive failures = amber, 7+ days stale = red
- Health page is purely informational with no action buttons
- Next.js runs in standalone Docker mode with multi-stage build
- Full Docker Compose stack validates and is deployable
</success_criteria>

<output>
After completion, create `.planning/phases/4/4-04-SUMMARY.md`
</output>
