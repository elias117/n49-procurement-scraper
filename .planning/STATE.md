# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.
**Current focus:** Phase 5 - Scheduling and Hardening (COMPLETE)

## Current Position

Phase: 5 of 5 (Scheduling and Hardening) — COMPLETE
Plan: 2 of 2 complete
Status: All Phase 5 plans complete — Scheduling and Hardening ready
Last activity: 2026-02-24 — 5-02 nightly scrape script, Docker prune, crontab installer

Progress: [##########] 100% (2/2 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: ~4.9 min
- Total execution time: ~69 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 1/1 | ~15min | ~15min |
| 2 | 4/4 | ~20min | ~5min |
| 3 | 4/4 | ~18min | ~4.5min |
| 4 | 4/4 | ~14min | ~3.5min |
| 5 | 2/2 | ~2min | ~1min |

**Recent Trend:**
- Last 5 plans: 4-02 (complete), 4-04 (complete), 4-03 (complete), 5-01 (complete), 5-02 (complete)
- Trend: accelerating

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: Browser Use + instructor chosen for generalist scraping across 63 diverse portal layouts (instructor recommended over LangExtract per Phase 2 research)
- [Pre-phase]: pgvector chosen over Elasticsearch — single data store for structured + vector data
- [Pre-phase]: Single EC2 + Docker Compose — simple and cheap for internal tool
- [Pre-phase]: APScheduler over Celery — no broker needed for a single nightly batch
- [Pre-phase]: text-embedding-3-small locked as embedding model — model changes require full re-indexing
- [Phase 1]: Stub services for Phase 1 — scraper sleeps, web returns JSON health endpoint
- [Phase 1]: Terraform lock file committed for reproducible provider versions
- [Phase 1]: Port 443 verified as production-only concern (EC2 target)
- [Phase 1]: rsync installed on EC2 (not in AL2023 by default)
- [Phase 1]: cronie installed on EC2 for certbot renewal cron
- [Phase 2]: Pydantic v2 BaseModel for all data models (matches DB schema exactly)
- [Phase 2]: psycopg2 direct connections, no pool needed for sequential batch processing
- [Phase 2]: xmax=0 trick in RETURNING clause to distinguish new vs updated upsert rows
- [Phase 2]: Embedding vectors passed as string format '[0.1, 0.2, ...]' for pgvector compatibility
- [Phase 2]: BOM stripping added defensively in _parse_csv as well as in httpx utf-8-sig decoding
- [Phase 2]: Lazy tiktoken encoder initialization to avoid import-time overhead
- [Phase 2]: Lazy imports for browser-use in scraper modules (Python 3.9 dev vs 3.11+ Docker runtime)
- [Phase 2]: Two-layer retry: instructor max_retries for validation, tenacity for rate limits/connection errors
- [Phase 2]: Browser page access fallback: current_page then context.pages for browser-use version compatibility
- [Phase 2]: Per-portal error isolation with try/except in process_portal (failed portal returns error dict)
- [Phase 2]: Sequential portal processing (not parallel) for 4GB container memory constraint
- [Phase 2]: classify_portal uses name match for CanadaBuys, URL match for BidsAndTenders, fallback to browser
- [Phase 2]: sys.path fix in main.py for Docker CMD direct invocation compatibility
- [Phase 2]: User-Agent header required for CanadaBuys CSV download (403 without it)
- [Phase 2]: JSONB columns need ::jsonb cast in upsert CTE input_rows
- [Phase 2]: execute_values returns rows directly (not via fetchone) when fetch=True
- [Phase 3]: FastAPI root_path=/api with nginx proxy_pass trailing slash for prefix stripping
- [Phase 3]: Stored generated tsvector column for index-aligned FTS (avoids expression mismatch)
- [Phase 3]: Docker build context set to project root for package-qualified imports
- [Phase 3]: Python 3.9 compat: Optional[X] with __future__ annotations instead of X | None union syntax
- [Phase 3]: Browse mode (empty query) falls back to posting_date DESC sort since relevance requires a query
- [Phase 3]: Three SQL paths (browse, keyword-only, full hybrid) for clarity over conditional SQL assembly
- [Phase 3]: bleach.clean with strip=True for XSS-safe ts_headline output -- strips all HTML except <mark> tags
- [Phase 3]: ts_headline applied AFTER pagination on final result set only to avoid performance pitfall
- [Phase 3]: Browse mode uses LEFT(COALESCE) for snippets since ts_headline requires a query
- [Phase 3]: Exact match uses ILIKE with CASE-based ranking: title=0, source_listing_id=1, description=2
- [Phase 3]: Benchmark tests use httpx against live API (not TestClient) to validate full HTTP stack
- [Phase 3]: Integration tests skip automatically when DATABASE_URL not set (CI-safe)
- [Phase 4]: Auth.js v5 credentials provider with bcryptjs in Next.js layer (not API layer) for password verification
- [Phase 4]: JWT session strategy with 30-day maxAge for persistent BD team login
- [Phase 4]: Standalone Next.js output mode for Docker deployment readiness
- [Phase 4]: NuqsAdapter at root layout level for URL-encoded search state in all pages
- [Phase 4]: Suspense boundary wrapping DashboardContent because nuqs useQueryStates reads URL search params at render time
- [Phase 4]: setFilter helper resets page to 1 to prevent empty-page navigation after filter changes
- [Phase 4]: AbortController cancels in-flight requests when params change to prevent stale responses
- [Phase 4]: Result cards show only search API fields; status and classification_codes deferred to detail panel (4-03)
- [Phase 4]: Staleness thresholds locked: healthy (<3 fails, <7 days), warning (3+ fails), stale (7+ days)
- [Phase 4]: Health page purely informational -- no action buttons
- [Phase 4]: Multi-stage Docker build copies standalone + static + public to runner
- [Phase 4]: Added level/province to portal_health API query for table columns
- [Phase 4]: Sheet slide-out from right with sm:max-w-[600px] for listing detail -- results list stays visible behind overlay
- [Phase 4]: Read-before-update pattern for last_visited_at: GET then PUT, previous value used for New badge comparison
- [Phase 4]: SessionProvider at dashboard layout level wraps all dashboard pages for useSession access
- [Phase 4]: Nav accepts children prop for extensible content like freshness indicator
- [Phase 5]: restart: always over unless-stopped for reboot recovery
- [Phase 5]: Scraper sleep infinity for cron-based docker compose exec invocations
- [Phase 5]: 50MB max log per service (10m x 5 files)
- [Phase 5]: Real sha256 digests fetched from registry for pgvector and nginx
- [Phase 5]: flock -n non-blocking lock: skip run if previous still active (no queue, no wait)
- [Phase 5]: CRON_TZ=America/Toronto over ET for DST-aware IANA timezone handling
- [Phase 5]: Retention cleanup runs unconditionally after scrape (even if scrape fails)
- [Phase 5]: docker system prune --filter until=168h protects recently-built images
- [Phase 5]: install-crontab.sh replaces full crontab (idempotent)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2]: ~~Investigate CanadaBuys API~~ RESOLVED: CanadaBuys has structured CSV open data files — zero-cost ingestion path via direct download
- [Phase 2]: ~~Benchmark LLM API cost on 5 representative portals~~ RESOLVED: 897 CanadaBuys listings embedded for ~$0.008 (385K tokens). Embedding cost is negligible.
- [Phase 2]: Audit robots.txt compliance — deferred to execution, robots.txt check recommended but not blocking

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 5-02 — Phase 5 Scheduling and Hardening complete (all 2 plans). ALL 5 PHASES COMPLETE.
Resume file: Project complete
