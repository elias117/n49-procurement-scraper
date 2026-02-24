# Project Research Summary

**Project:** Procurement Intelligence Platform
**Domain:** Government procurement portal scraping + AI extraction + semantic search (Canadian, internal BD tool)
**Researched:** 2026-02-24
**Confidence:** HIGH (stack verified against official sources; features confirmed by competitive analysis; architecture patterns well-established; pitfalls drawn from multiple production sources)

## Executive Summary

This is an internal business development tool for a team monitoring 63 Canadian government procurement portals. The fundamental challenge is aggregating JS-rendered, heterogeneous portal data into a unified search interface — a problem that traditional scrapers cannot solve reliably at this scale. The recommended approach pairs browser-use (AI-driven browser automation) with LangExtract (Google's structured field extraction library) to replace 63 custom scrapers with one generalist pipeline driven by per-portal YAML configs. PostgreSQL with pgvector eliminates the need for a separate vector database, and a Next.js frontend with hybrid search (keyword + semantic) delivers the natural language querying explicitly required by the project brief. All services run on a single EC2 instance in ca-central-1 via Docker Compose, managed by Terraform.

The architecture is deliberately simple and unidirectional: a nightly scheduler triggers the scraper, which writes to PostgreSQL, which the Next.js frontend reads. The scraper never talks to the frontend; the frontend never triggers scraping. This separation means each layer can be built and tested independently. The MVP question this platform must answer is: "What new government opportunities posted since yesterday are relevant to us?" — and research confirms that nightly batch scraping with hybrid search is the correct answer for this team's workflow, not real-time streaming or complex ML-scored recommendations.

The two biggest risks are silent data quality failures (portals scraped successfully but extracting zero or wrong listings) and LLM API cost explosion (AI browser agents accumulating token context across 63 portals). Both risks are preventable with per-portal yield tracking and cost benchmarking before scaling to the full portal set, but both will cause serious trust or budget problems if discovered post-deployment. The schema design, audit logging, and Docker configuration must be correct in Phase 1 before data populates — these cannot be retrofitted cheaply.

## Key Findings

### Recommended Stack

The stack is split across two runtimes: Python 3.12 for the scraper pipeline and Node.js 20 (LTS) for the Next.js frontend. On the Python side, browser-use 0.11.12 and Playwright 1.58.0 handle JS-rendered portal navigation, LangExtract 1.1.1 extracts structured fields via LLM, FastAPI 0.133.0 exposes internal API endpoints, and SQLAlchemy 2.0 with asyncpg handles async database writes. APScheduler replaces Celery for nightly job scheduling — Celery's broker (Redis/RabbitMQ) is unnecessary overhead for a single nightly batch. On the frontend, Next.js 16 with App Router and React 19.2 is the correct choice for greenfield; Auth.js v5 handles credentials auth. PostgreSQL 17 with pgvector 0.8.1 is the single data store, handling both structured queries (tsvector GIN index) and semantic search (HNSW vector index), eliminating the need for Elasticsearch or a separate vector database.

**Core technologies:**
- **browser-use 0.11.12**: AI-driven browser automation — handles JS-rendered portals across 63 diverse layouts without per-site selectors
- **LangExtract 1.1.1**: Structured field extraction from page text — Google-backed, source-grounded extraction with schema enforcement reduces hallucination risk
- **PostgreSQL 17 + pgvector 0.8.1**: Single data store for structured + vector data — eliminates dual-write complexity of a separate vector DB; HNSW index for <100ms semantic search at this scale
- **FastAPI 0.133.0**: Internal API layer — async-first, Pydantic-native, auto-generates OpenAPI docs
- **Next.js 16 (App Router)**: Frontend framework — Server Components for data-heavy dashboard; required for hybrid search UI; Auth.js v5 for credentials auth
- **APScheduler 3.x**: In-process nightly job scheduling — simpler than Celery for a single 2 AM batch across 63 portals
- **OpenAI text-embedding-3-small**: Embedding generation — $0.00002/1K tokens; 1,536 dimensions within pgvector HNSW 2,000-dimension limit
- **Terraform + Docker Compose on EC2 (ca-central-1)**: Infrastructure — Canadian data sovereignty; t3.large (8GB) recommended over t3.medium given Playwright memory needs

See `.planning/research/STACK.md` for full version table, alternatives considered, and installation commands.

### Expected Features

The BD team has one daily question: what is new and relevant since yesterday? Everything else is noise. Research against MERX, CanadaBuys, GCFinder, Sweetspot, and Tendium confirms the minimum table stakes and the features worth building in v1 vs. deferring.

**Must have (table stakes — missing = platform feels broken):**
- Nightly scraper pipeline + AI field extraction — the entire platform collapses without this; ship nothing until data populates reliably
- Keyword search (full-text across title + description) — universal expectation across all comparable platforms
- Filter: closing date range (default to open-only, future dates) — deadlines are the primary time constraint for BD
- Filter: region/province, portal source, solicitation type, posting date — expected by any team monitoring Canadian portals
- Filter: category/commodity code (NAICS, UNSPSC, GSIN) — how opportunities are scoped; requires AI extraction to be reliable
- Natural language search — explicitly required in PROJECT.md; pgvector is already in the stack
- Listing detail view with source URL link — team must read the full listing and navigate to the portal to act
- Data freshness indicator + scraper health status — trust is fragile; team must know when data is stale
- Simple username/password authentication — required for any internal deployment

**Should have (differentiators — elevate above manual portal checking):**
- Hybrid search (keyword + semantic combined via RRF) — neither alone is sufficient; pure keyword misses synonyms, pure semantic misses exact codes
- "New today" / "New since last visit" badges — daily-use tool; this is the hook that makes it habitual
- Scraper run status dashboard (per-portal last-run, success/fail, listing count) — essential for diagnosing silent extraction failures
- Document attachment links and contact info display — extracted fields that save a portal round-trip
- Filter: estimated contract value, sort controls — P1 but lower urgency than date/region filters

**Defer to v2+:**
- Email alerts (PROJECT.md explicitly defers; adds SMTP infrastructure)
- Saved search profiles (useful friction-reducer, not blocking adoption)
- Amendment history tracking (moderate complexity; tolerate gaps in v1)
- Cross-portal deduplication (complex to get right; tolerate duplicates in v1)
- Bookmarks/flags per listing (validate daily use first)

**Confirmed anti-features (never build):**
- CRM/pipeline management, bid scoring, proposal writing, SSO/RBAC, real-time scraping, mobile app — scope creep traps confirmed by competitor analysis

See `.planning/research/FEATURES.md` for the full prioritization matrix and feature dependency graph.

### Architecture Approach

The system is a unidirectional data pipeline: Scheduler triggers Scraper, Scraper writes to PostgreSQL, Next.js reads from PostgreSQL. There is no feedback loop — Next.js cannot trigger scraping, and the scraper has no HTTP interface facing the frontend. This strict separation is what makes the system testable and debuggable in phases. All services run on a single EC2 instance in a Docker Compose network, with Nginx handling TLS termination and reverse proxying. The Scraper container runs both FastAPI (for internal API surface) and APScheduler (for nightly cron). Query-time hybrid search combines PostgreSQL tsvector (keyword ranking) and pgvector cosine similarity (semantic ranking) merged with Reciprocal Rank Fusion at the application layer — no additional search service required.

**Major components:**
1. **Scheduler (APScheduler or Ofelia)** — fires nightly scrape at 2 AM ET; no knowledge of portal configs, only fires the trigger
2. **Scraper Pipeline (Python)** — loads 63 portal configs from YAML/DB, navigates portals via browser-use + Playwright, extracts fields via LangExtract, generates embeddings, upserts to PostgreSQL with audit logging
3. **PostgreSQL 17 + pgvector** — single source of truth; GIN index for keyword search, HNSW index for semantic search; scrape_runs audit table for observability
4. **Next.js App (App Router)** — serves BD team dashboard; Server Actions/API routes execute hybrid search; Auth.js v5 for session management; TanStack Table for filterable/sortable listings
5. **Nginx** — reverse proxy + TLS termination; routes /api/ to FastAPI, everything else to Next.js

Key patterns: embed listings at insert time (never at query time), store portal configs as data not code, use upsert semantics (INSERT ... ON CONFLICT DO UPDATE) on (portal_id, listing_id) composite key, clean HTML to plain text before LangExtract, batch embedding API calls.

See `.planning/research/ARCHITECTURE.md` for the full system diagram, database schema SQL, project directory structure, and anti-patterns.

### Critical Pitfalls

Research identified 5 critical pitfalls that cause rewrites or loss of team trust, and 5 moderate pitfalls that compound into expensive problems if not addressed early. All critical pitfalls are Phase 1 concerns — they cannot be retrofitted cheaply.

1. **Silent extraction failure across portals** — A portal changes layout; the scraper reports "success" but extracts zero listings for weeks. Prevent by tracking per-portal listing yield in a scrape_runs audit table and alerting when yield drops to 0 after previously being positive. This is a Phase 1 schema requirement.

2. **LLM hallucination on critical fields** — LangExtract infers closing dates or contract values that aren't on the page. Prevent by using LangExtract's source-grounding feature, adding post-extraction validation rules (closing_date >= posting_date, value within plausible range), and storing raw extracted strings alongside parsed values. Phase 1 extraction schema design.

3. **Playwright/Chromium memory exhaustion** — Without explicit browser context cleanup and Docker shm_size configuration, zombie Chromium processes accumulate and OOM the EC2 instance mid-run. Prevent by always closing browser contexts in try/finally blocks, setting shm_size: '2gb' in Docker Compose, limiting concurrency to 3-5 parallel portals, and setting container mem_limit: 4g. Phase 1 Docker configuration.

4. **LLM API cost explosion at scale** — Browser-use agents accumulate token context across navigation steps; at 63 portals the nightly cost can reach $50-200+. Prevent by benchmarking token costs on 5 representative portals before scaling to 63, using cheapest capable model (Gemini Flash or GPT-4o-mini), hashing page content to skip unchanged portals, and setting per-run token budgets with hard stops. Establish baseline before Phase 2 scale-out.

5. **Embedding model lock-in** — Switching embedding models invalidates all stored vectors, degrading semantic search silently. Prevent by storing the model name with every embedding, treating model changes as breaking changes requiring full re-indexing, and locking text-embedding-3-small as the stable choice from Phase 1. Never switch without a full re-embedding migration.

Additional moderate pitfalls: timezone corruption (use TIMESTAMPTZ; build a per-portal timezone registry), same-portal deduplication failure (upsert semantics from day 1), bot detection/rate limiting (randomize timing, add jitter), EC2 single point of failure (dead-man monitoring alert if no new listings in 26h), pgvector HNSW index missing at scale (create in initial schema migration, before data).

See `.planning/research/PITFALLS.md` for the full pitfall catalog, technical debt patterns, security mistakes, and the "Looks Done But Isn't" production checklist.

## Implications for Roadmap

Research strongly indicates a 5-phase build sequence driven by data dependencies: the scraper must produce valid data before search can be tuned, and search logic must be defined before the UI is finalized. The architecture's unidirectional data flow maps cleanly onto this sequence.

### Phase 1: Infrastructure and Data Foundation

**Rationale:** Every other phase depends on PostgreSQL being live with the correct schema. Schema mistakes (wrong date types, missing audit tables, wrong upsert keys) are the most expensive to fix retroactively. Infrastructure (Terraform, Docker Compose, Nginx, Certbot) must exist before any service can be deployed. This phase has no external dependencies.

**Delivers:** Provisioned EC2 instance in ca-central-1, Docker Compose scaffold with all services defined, PostgreSQL 17 + pgvector schema with all tables (listings, portals, scrape_runs), HNSW index, TIMESTAMPTZ columns, composite unique constraints, upsert semantics, Terraform remote state in S3, Nginx + TLS configuration.

**Addresses:** Authentication scaffolding (Auth.js v5 setup), data schema for all extracted fields including embedding_model column.

**Avoids:** Silent schema debt (TIMESTAMPTZ, upsert keys, audit table — all Phase 1 requirements from PITFALLS.md); Terraform state stored locally (configure S3 backend before first apply); PostgreSQL exposed on public interface.

**Research flag:** Standard patterns. Terraform + Docker Compose + PostgreSQL setup is well-documented. Skip `/gsd:research-phase` for this phase.

### Phase 2: Scraper Pipeline (Core Value)

**Rationale:** No frontend value exists until listings populate the database. This is the hardest and most novel engineering in the project — browser-use + LangExtract is newer territory and must be proven correct before the team can trust anything downstream. Run scraper manually (python main.py) during this phase; no scheduler yet.

**Delivers:** Portal config loader (YAML for 63 portals), browser-use + Playwright agent for JS-rendered navigation, LangExtract extraction schema with post-extraction validation, embedding generation pipeline (text-embedding-3-small), PostgreSQL upsert writer with scrape_runs logging, rate limiting and jitter per portal. Cost baseline measured on 5 representative portals before scaling to all 63.

**Addresses:** Nightly scraper pipeline (P0 feature), AI field extraction (P0), data freshness tracking, scraper health status (P1), document attachment links, contact info.

**Avoids:** Silent extraction failures (per-portal yield tracking built here), LLM hallucination (post-extraction validation built here), Playwright memory exhaustion (Docker shm_size and concurrency limits configured here), LLM API cost explosion (benchmark before scaling to all 63), Playwright "works in dev but not Docker" (use official mcr.microsoft.com/playwright/python base image).

**Research flag:** Needs `/gsd:research-phase`. Browser-use and LangExtract production integration patterns are newer territory. Specifically: CanadaBuys API surface should be investigated before building a full browser scraper for federal listings — an official API is significantly more reliable.

### Phase 3: Search Layer

**Rationale:** Hybrid search (keyword + semantic via RRF) is the core UI contract. Defining and validating the query logic before building the React UI prevents rebuilding API routes when search behavior is tuned. This phase requires real data in the DB from Phase 2.

**Delivers:** PostgreSQL full-text search queries (tsvector + GIN index), pgvector cosine similarity queries with HNSW, Reciprocal Rank Fusion merge logic at the application layer, SQL filter composition (date range, region, portal source, category, contract value, solicitation type), pagination logic, semantic search validated against 20 real procurement queries from the BD team.

**Addresses:** Keyword search (P0), natural language search (P0), hybrid combined search (P1), filter suite, sort controls.

**Avoids:** Keyword vs. semantic search confusion (implement hybrid from the start, not as a later addition), embedding model lock-in (model locked before search is built), pgvector HNSW index missing at scale (already in schema from Phase 1).

**Research flag:** Mostly standard patterns. RRF hybrid search in PostgreSQL is well-documented. The nuance is query routing (when to trigger semantic vs. keyword vs. hybrid) — may need a brief research spike but not a full research phase.

### Phase 4: Web Application

**Rationale:** The frontend is the delivery mechanism; build it last against a stable search API and proven data layer. Next.js App Router with Server Components is the correct model for this data-heavy dashboard, and it can be built cleanly once the API contracts from Phase 3 are locked.

**Delivers:** Next.js 16 App Router application with Auth.js v5 credentials login, search bar + filter panel UI (shadcn/ui components, TanStack Table), listing detail view with source URL link, "New today" badges, data freshness indicator, URL-synced filter state (nuqs), scraper health dashboard page.

**Addresses:** Authentication (P0), listing detail view (P0), source URL link (P0), filter: category/value/solicitation type (P1), sort controls (P1), "New today" badge (P1), scraper health dashboard (P1), contact info display (P1).

**Avoids:** Next.js 16 async params errors (enforce TypeScript strict mode from day 1; all route params, cookies(), headers() are now async); client-side state bloat (Server Components handle most data fetching; TanStack Query for interactive search state only).

**Research flag:** Standard patterns. Next.js App Router + shadcn/ui is heavily documented. Skip `/gsd:research-phase`.

### Phase 5: Scheduling, Observability, and Hardening

**Rationale:** Automate only after the manual pipeline is proven correct. Scheduling, monitoring, and production hardening come last — after the team has validated that scraper output is trustworthy and search results are useful.

**Delivers:** Ofelia or APScheduler nightly cron at 2 AM ET, dead-man alert (CloudWatch alarm if no new listings in 26+ hours), EC2 memory CloudWatch alarm at 80%, per-portal yield alerting (0 listings after non-zero baseline), Docker Compose production hardening (pinned image digests, restart: always, log rotation, separate docker-compose.prod.yml), robots.txt compliance audit for all 63 portals.

**Addresses:** Data freshness indicator (automated), scraper health status (operational alerting layer).

**Avoids:** EC2 single point of failure without monitoring, silent per-portal failures going undetected, zombie browser process accumulation going undetected, Docker Compose production misuse.

**Research flag:** Standard patterns. CloudWatch + Docker Compose hardening is well-documented. Consider whether to use Ofelia (external Docker cron) vs. APScheduler in-process — either works; the architectural question is whether to use AWS EventBridge as the external trigger for resilience.

### Phase Ordering Rationale

- **Data before UI:** The scraper pipeline (Phase 2) must produce valid data before the search layer (Phase 3) can be tuned, and the search API must be defined before the UI (Phase 4) is finalized. This sequencing prevents building React components against a moving API target.
- **Schema is irreversible:** TIMESTAMPTZ columns, upsert constraints, audit tables, and the HNSW index must exist from Phase 1. Adding them retroactively requires data migrations and downtime.
- **Manual before automated:** Run the scraper manually in Phase 2 to validate correctness. Add the scheduler in Phase 5 only after the pipeline is trusted. This prevents debugging cron timing issues while simultaneously debugging extraction quality.
- **Cost before scale:** Benchmark LLM API costs on 5 representative portals in Phase 2 before enabling all 63. This prevents a $200/night surprise in production.
- **Pitfalls mapped to phases:** All 5 critical pitfalls from PITFALLS.md are addressed in Phases 1-2. By Phase 3, the data layer should be trustworthy enough to build search on top of it.

### Research Flags

Phases likely needing `/gsd:research-phase` during planning:
- **Phase 2 (Scraper Pipeline):** Browser-use + LangExtract production integration is newer territory with limited production case studies. Specifically needs research on: CanadaBuys API surface (may avoid browser scraping for federal listings entirely), browser-use concurrency patterns for batch portal scraping, LangExtract source-grounding validation implementation, and cost optimization patterns for AI browser agents.

Phases with standard patterns (can skip `/gsd:research-phase`):
- **Phase 1 (Infrastructure):** Terraform + EC2 + Docker Compose + PostgreSQL + pgvector are all well-documented. Schema design should follow the SQL in ARCHITECTURE.md directly.
- **Phase 3 (Search):** RRF hybrid search with pgvector + tsvector is well-documented. May need a brief spike on query routing heuristics (keyword vs. semantic vs. hybrid trigger) but not a full research phase.
- **Phase 4 (Web App):** Next.js 16 App Router + shadcn/ui + Auth.js v5 are heavily documented. Follow official patterns.
- **Phase 5 (Scheduling + Hardening):** Standard DevOps patterns. CloudWatch + Docker Compose hardening is well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All library versions verified on PyPI/npm/official sources as of 2026-02-24. APScheduler vs. Celery decision is MEDIUM (reasoned, not benchmarked). Hybrid search RRF implementation detail is MEDIUM (pattern documented, implementation left to Phase 3). |
| Features | HIGH | Confirmed against 6+ competitive platforms (MERX, CanadaBuys, GCFinder, Sweetspot, Tendium, Capture2Proposal). Anti-features aligned with PROJECT.md explicit exclusions. |
| Architecture | HIGH | Unidirectional pipeline pattern is well-established. Browser-use + LangExtract integration is documented but has lower production track record than established libraries — MEDIUM confidence for the scraper-specific component. Database schema is directly from pgvector documentation. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls 1-4 are confirmed across multiple sources (Browserless, Firecrawl, Playwright GitHub Issues, production post-mortems). Pitfall 5 (embedding lock-in) is well-understood in the vector DB community. Browser-use agent cost behavior extrapolated from general LLM agent patterns rather than browser-use-specific production data. |

**Overall confidence:** HIGH for infrastructure, schema, and frontend phases. MEDIUM-HIGH for scraper pipeline phase (browser-use + LangExtract is the least-documented component in production settings).

### Gaps to Address

- **CanadaBuys API:** Before building a browser scraper for federal procurement listings, investigate whether CanadaBuys exposes a stable REST or search API. If it does, use it — an official API eliminates the largest scraping fragility for the highest-volume federal portal. Validate in Phase 2 planning.

- **LLM cost baseline:** The per-night LLM cost estimate ($5-200 range) is too wide to plan around. The Phase 2 plan must include a cost benchmarking step on 5 representative portals before enabling all 63. The model choice (Gemini Flash vs. GPT-4o-mini vs. GPT-4o) depends on this measurement.

- **Hybrid search query routing:** Research documents the hybrid search pattern (tsvector + pgvector via RRF) but does not resolve the query routing heuristic — when does a query trigger keyword-only vs. semantic-only vs. hybrid? This is a product/UX decision that needs validation with the BD team before Phase 3 implementation. A reasonable default: always run hybrid, weight by query characteristics.

- **63 portal robots.txt compliance:** Legal and operational compliance status of scraping all 63 portals is not validated. The "Looks Done But Isn't" checklist in PITFALLS.md flags robots.txt review as a prerequisite for production. This should be audited in Phase 2 before the full portal set is enabled.

- **Next.js 16 vs. 15.5 decision:** STACK.md recommends Next.js 16 for greenfield but notes Next.js 15.5 as a valid fallback if the team is more comfortable with it. The async params breaking changes in Next.js 16 require careful attention. Confirm the team's preference before Phase 4 kickoff.

## Sources

### Primary (HIGH confidence — official sources, verified versions)
- browser-use PyPI / GitHub — version 0.11.12, architecture, LangChain compatibility
- LangExtract PyPI / GitHub / Google Developers Blog — version 1.1.1, source-grounding feature, extraction schema
- FastAPI PyPI — version 0.133.0
- SQLAlchemy release blog — version 2.0.46
- pgvector GitHub — version 0.8.1, HNSW parameters, dimension limits
- Next.js 16 release blog + upgrade guide — version 16.1.6, breaking changes (async params, proxy.ts)
- Auth.js v5 docs — credentials provider, Next.js 16 compatibility
- OpenAI embeddings docs — text-embedding-3-small pricing, dimensions
- PostgreSQL pgvector Docker Hub — pgvector/pgvector:pg17 canonical image
- MERX, CanadaBuys, GCFinder, Sweetspot, Tendium — feature benchmarking

### Secondary (MEDIUM confidence — community consensus, multiple sources agree)
- ParadeDB, Jonathan Katz — hybrid search RRF implementation in PostgreSQL
- Ofelia GitHub + Docker cron guides — scheduling pattern for Docker Compose
- Browserless, Firecrawl, Grepsr — web scraping production pitfalls
- ScrapingBee — 2025 web scraping challenges (Playwright vs. detection)
- DEV Community — RRF hybrid search implementation patterns

### Tertiary (MEDIUM confidence — extrapolated or inferred)
- LLM API cost estimates for browser-use agents at 63-portal scale — extrapolated from general agentic AI cost patterns; needs empirical validation in Phase 2
- APScheduler performance for this specific use case — reasoned from architecture constraints, not benchmarked
- browser-use concurrency patterns for batch scraping — documented for single-portal use; multi-portal batch behavior inferred from Playwright concurrency patterns

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
