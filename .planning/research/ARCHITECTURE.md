# Architecture Patterns

**Project:** Procurement Intelligence Platform
**Domain:** Multi-source web scraping + structured search (government procurement)
**Researched:** 2026-02-24
**Confidence:** HIGH (core patterns well-established; Browser Use + LangExtract are newer but documented)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        EC2 Instance (ca-central-1)              │
│                        Docker Compose Network                   │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────────────────────────┐  │
│  │  Scheduler   │───▶│         Scraper Pipeline             │  │
│  │  (cron/      │    │  ┌────────────┐  ┌───────────────┐  │  │
│  │   ofelia)    │    │  │ Browser Use│  │  LangExtract  │  │  │
│  └──────────────┘    │  │ + Playwright│─▶│  (field      │  │  │
│                       │  └────────────┘  │   extraction) │  │  │
│                       │                  └───────┬───────┘  │  │
│                       └──────────────────────────┼──────────┘  │
│                                                  │             │
│                       ┌──────────────────────────▼──────────┐  │
│                       │         PostgreSQL + pgvector        │  │
│                       │  ┌─────────────┐  ┌──────────────┐ │  │
│                       │  │  Listings   │  │  Embeddings  │ │  │
│                       │  │  (SQL rows) │  │  (vector col)│ │  │
│                       │  └─────────────┘  └──────────────┘ │  │
│                       └──────────────────────────┬──────────┘  │
│                                                  │             │
│  ┌──────────────────────────────────────────────▼──────────┐  │
│  │              Next.js Application (App Router)            │  │
│  │  ┌────────────────────┐  ┌────────────────────────────┐ │  │
│  │  │  Search API Routes │  │  Auth Middleware            │ │  │
│  │  │  (hybrid SQL +     │  │  (simple session/cookie)   │ │  │
│  │  │   pgvector)        │  └────────────────────────────┘ │  │
│  │  └────────────────────┘                                 │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │  React UI: Search Bar, Filter Panel, Listing Cards │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────┐                                              │
│  │  Nginx       │◀──── Internet (BD Team browsers)            │
│  │  (reverse    │                                              │
│  │   proxy/TLS) │                                              │
│  └──────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
```

**Data flows in one direction:** Scheduler triggers scraper → scraper writes to Postgres → Next.js reads from Postgres → UI renders results. The scraper never talks to Next.js; Next.js never triggers scraping.

---

## Component Responsibilities

| Component | Responsibility | Communicates With | Technology |
|-----------|---------------|-------------------|------------|
| **Scheduler** | Triggers nightly scrape job at configured time (e.g., 2 AM ET) | Scraper pipeline (exec or HTTP trigger) | Ofelia (Docker cron) or native cron in scraper container |
| **Scraper Pipeline** | Navigates portals, renders JS, extracts structured fields, embeds text, writes to DB | PostgreSQL (writes), Browser Use + Playwright (browser), LangExtract (extraction), LLM API (inference) | Python, Browser Use, Playwright, LangExtract, asyncio |
| **Portal Config Store** | Holds the 63 portal configs — URL, portal type, field mappings, scrape hints | Scraper reads at job start | YAML files or DB table |
| **PostgreSQL + pgvector** | Single source of truth for all listings. Stores structured fields + vector embeddings in same rows | Scraper writes, Next.js reads | PostgreSQL 16+, pgvector extension |
| **Next.js App** | Serves the BD team UI. Handles auth, hybrid search queries, filter logic, result display | PostgreSQL (reads via server-side), browser clients (via SSR/API routes) | Next.js 15, TypeScript, Tailwind, Drizzle ORM |
| **Nginx** | Reverse proxy, TLS termination, routes traffic to Next.js port | Next.js container, internet | Nginx |
| **LLM API** | Powers Browser Use agent decisions + LangExtract field extraction | Scraper pipeline (outbound HTTPS) | OpenAI / Anthropic / Google (external) |

### What Each Component Does NOT Do

- **Scraper** does not serve HTTP to the UI. No shared API between scraper and frontend.
- **Next.js** does not trigger or orchestrate scraping. It is read-only against the database.
- **PostgreSQL** does not embed text — embedding generation happens in the scraper pipeline before INSERT.
- **Scheduler** does not know about portal configs — it only fires "run scrape job".

---

## Data Flow

### Nightly Scrape Flow

```
1. Scheduler fires at 2 AM ET
       │
       ▼
2. Scraper loads portal config list (63 portals: URL, type, hints)
       │
       ▼  (for each portal, with concurrency controls)
3. Browser Use agent + Playwright
       - Renders portal page in headless Chromium
       - Agent navigates listing pages (JS-rendered, paginated, varied formats)
       - Extracts raw HTML / text of each listing
       │
       ▼
4. LangExtract structured extraction
       - Input: raw listing text (per-listing)
       - Schema: title, description, posting_date, closing_date, portal_source,
                 naics_codes, unspsc_codes, category, region, contract_value,
                 budget_range, contact_info, document_links, amendment_history
       - Output: validated structured dict
       │
       ▼
5. Embedding generation
       - Concatenate title + description + key fields into embedding target string
       - Call embedding API (e.g., text-embedding-3-small)
       - Result: 1536-dimensional float vector
       │
       ▼
6. Upsert to PostgreSQL
       - INSERT ... ON CONFLICT (portal_id, listing_id) DO UPDATE
       - Structured columns + vector column updated atomically
       - Scrape run metadata logged (portal, count, errors, duration)
```

### User Search Flow

```
1. BD team submits query in Next.js UI
       │  (may be keyword: "IT consulting" or NL: "construction contracts Ontario")
       ▼
2. Next.js API route / Server Action receives query + filter params
       │
       ▼
3. Query classification (keyword vs. semantic)
       │
       ├── Keyword query → full-text SQL (tsvector + GIN index)
       │
       ├── Semantic/NL query → embed query string → pgvector cosine similarity
       │
       └── Mixed → Hybrid: both queries run, merged via Reciprocal Rank Fusion (RRF)
       │
       ▼
4. Apply SQL filters on top of ranked results
       - date range, region, category, portal source, contract value
       │
       ▼
5. Return paginated result set to React UI
       - Listing cards with all fields
       - Highlighted matched text (for keyword results)
```

### Embedding Strategy

The embedding target string combines high-signal fields:

```
"{title}. {description}. Region: {region}. Category: {category}. {naics_codes}."
```

Generate once at insert time. Store in `listings.embedding` (vector(1536) column).
Re-generate on update. Index with HNSW for fast approximate nearest-neighbor search.

---

## Recommended Project Structure

```
procurement-intel/
├── docker-compose.yml            # Defines all services
├── terraform/                    # AWS infra: EC2, VPC, security groups, EBS
│   ├── main.tf
│   └── variables.tf
│
├── scraper/                      # Python scraper pipeline (standalone service)
│   ├── Dockerfile
│   ├── pyproject.toml            # uv / pip dependencies
│   ├── main.py                   # Entry point — reads config, runs pipeline
│   ├── portals/
│   │   ├── config/               # YAML per-portal configs (63 files or one master YAML)
│   │   └── loader.py             # Parses portal configs
│   ├── browser/
│   │   └── agent.py              # Browser Use + Playwright orchestration
│   ├── extraction/
│   │   └── extractor.py          # LangExtract schema + extraction logic
│   ├── embedding/
│   │   └── embedder.py           # Text embedding generation
│   ├── db/
│   │   └── writer.py             # Postgres upsert logic, run logging
│   └── utils/
│       ├── ratelimit.py          # Per-portal delay + concurrency controls
│       └── logging.py
│
├── web/                          # Next.js app (frontend + API)
│   ├── Dockerfile
│   ├── package.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Main search page
│   │   ├── api/
│   │   │   ├── search/route.ts   # Hybrid search API route
│   │   │   └── auth/route.ts     # Auth endpoints
│   │   └── listings/[id]/page.tsx
│   ├── components/
│   │   ├── SearchBar.tsx
│   │   ├── FilterPanel.tsx
│   │   └── ListingCard.tsx
│   └── lib/
│       ├── db.ts                 # Drizzle ORM + pgvector queries
│       ├── search.ts             # Hybrid search logic (RRF)
│       └── auth.ts               # Session management
│
├── db/
│   └── migrations/               # SQL migration files (applied at startup)
│       ├── 001_initial_schema.sql
│       ├── 002_pgvector_index.sql
│       └── 003_run_log.sql
│
└── nginx/
    └── nginx.conf                # Reverse proxy config
```

---

## Database Schema (Core Tables)

```sql
-- Procurement listings
CREATE TABLE listings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id       TEXT NOT NULL,           -- Source portal identifier
  listing_id      TEXT NOT NULL,           -- Portal-native ID
  title           TEXT NOT NULL,
  description     TEXT,
  posting_date    DATE,
  closing_date    DATE,
  region          TEXT,
  province        TEXT,
  category        TEXT,
  naics_codes     TEXT[],
  unspsc_codes    TEXT[],
  contract_value  NUMERIC,
  budget_min      NUMERIC,
  budget_max      NUMERIC,
  contact_info    JSONB,
  document_links  TEXT[],
  amendment_history JSONB,
  source_url      TEXT,
  raw_text        TEXT,                    -- Original scraped text (for debugging)
  embedding       vector(1536),            -- pgvector embedding
  last_scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (portal_id, listing_id)           -- Upsert key
);

-- Full-text search index
CREATE INDEX listings_fts_idx ON listings
  USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'')));

-- Vector similarity index (HNSW — best speed/recall tradeoff)
CREATE INDEX listings_embedding_idx ON listings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Scrape run audit log
CREATE TABLE scrape_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at    TIMESTAMPTZ NOT NULL,
  finished_at   TIMESTAMPTZ,
  portal_count  INT,
  listings_new  INT,
  listings_updated INT,
  errors        JSONB,
  status        TEXT CHECK (status IN ('running', 'completed', 'failed'))
);

-- Portal registry (can also be YAML — DB gives queryability)
CREATE TABLE portals (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  url           TEXT NOT NULL,
  portal_type   TEXT,          -- 'html', 'api', 'js-heavy'
  province      TEXT,
  active        BOOLEAN DEFAULT TRUE,
  scrape_config JSONB          -- Browser Use hints, auth requirements, pagination
);
```

---

## Docker Compose Service Layout

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    volumes: [postgres_data:/var/lib/postgresql/data]
    environment: [POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]
    healthcheck: pg_isready

  scraper:
    build: ./scraper
    depends_on: [db]
    environment: [DATABASE_URL, OPENAI_API_KEY, ...]
    # No exposed ports — internal only

  scheduler:
    image: mcuadros/ofelia:latest
    depends_on: [scraper]
    volumes: [/var/run/docker.sock:/var/run/docker.sock]
    command: daemon --docker
    labels:
      ofelia.job-run.scrape.schedule: "0 0 2 * * *"   # 2 AM daily
      ofelia.job-run.scrape.container: "scraper"

  web:
    build: ./web
    depends_on: [db]
    environment: [DATABASE_URL, NEXTAUTH_SECRET, ...]
    expose: ["3000"]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    depends_on: [web]
    volumes: [./nginx/nginx.conf:/etc/nginx/conf.d/default.conf, certs:/etc/ssl]
```

---

## Build Order (Phase Dependency Sequence)

The component graph has a clear critical path. Build in this order to avoid integration dead-ends:

```
Phase 1: Infrastructure foundation
  Terraform (EC2 + VPC + EBS) → Docker Compose scaffold → PostgreSQL + pgvector + schema
  └── Reason: Everything else depends on the DB being live and migrations applied

Phase 2: Scraper pipeline
  Portal config loader → Browser Use + Playwright agent → LangExtract extraction
  → Embedding generation → DB writer
  └── Reason: No frontend value until listings exist in the database

Phase 3: Search layer
  Hybrid search query (RRF) → SQL filter composition → pgvector HNSW index tuning
  └── Reason: Search logic is the core UI contract; define before building UI

Phase 4: Web application
  Next.js auth → Search API route → Filter UI → Listing detail view
  └── Reason: Frontend is the delivery mechanism; build last against stable data

Phase 5: Scheduler + observability
  Ofelia cron config → Scrape run logging → Error alerting
  └── Reason: Automate only after the manual pipeline is proven correct
```

**Critical dependency:** The scraper must produce valid listings in the DB before the search layer can be meaningfully tested. Run scraper manually (python main.py) for Phase 2 development — no scheduler needed until Phase 5.

---

## Scaling Considerations

| Concern | On Single EC2 (v1) | If Scaling Later |
|---------|-------------------|-----------------|
| Scraper concurrency | 5-10 portals in parallel with asyncio; more risks blocks | Split into scraper workers; use Redis queue |
| Database size | ~5K listings/night fits easily on gp3 EBS; vector index in RAM | Read replica for search queries; partition by year |
| Search latency | HNSW index returns results in <100ms at this scale | Add connection pooling (pgBouncer); cache hot queries |
| LLM API costs | Batch embedding calls; use small model (text-embedding-3-small) | Evaluate local embedding model (e2e cost vs. latency) |
| Playwright memory | Each browser context ~200MB; limit concurrent contexts | Use Browserbase or dedicated browser service |
| Next.js traffic | Internal team (<20 users); single Node process is fine | Vercel deployment or horizontal scaling |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: One Scraper Per Portal
**What:** Write portal-specific selectors and scraping logic for each of the 63 portals.
**Why bad:** Maintenance nightmare. Each portal change breaks a dedicated scraper. 63 portals = 63 maintenance surfaces. This is precisely why Browser Use + LangExtract were chosen.
**Instead:** Use the AI agent generalist approach. One scraper code path, per-portal config (URL + hints only). LangExtract handles field variance.

### Anti-Pattern 2: Embedding at Query Time
**What:** When a user searches, embed the query AND re-embed stored content for comparison.
**Why bad:** Recomputing 5,000 embeddings per search query is catastrophically slow and expensive.
**Instead:** Embed listings once at insert time. Store in `vector` column. At query time, embed only the user's search string (1 API call), then use pgvector for nearest-neighbor lookup.

### Anti-Pattern 3: Separate Search Service
**What:** Add Elasticsearch or Opensearch alongside PostgreSQL for full-text search.
**Why bad:** Dual-write complexity, sync drift, extra infra cost, another failure point on a single EC2 box.
**Instead:** PostgreSQL's built-in tsvector + GIN index handles keyword search well at this scale. pgvector handles semantic. Hybrid search via RRF needs no additional service.

### Anti-Pattern 4: Scraper Triggered by Next.js
**What:** Next.js API route triggers scraping on-demand (user clicks "refresh").
**Why bad:** Scraping 63 portals takes hours. HTTP timeout will kill the request. State management across browser sessions is fragile.
**Instead:** Strict unidirectional flow. Scheduler fires scraper independently. Next.js is read-only. If on-demand refresh is needed later, use a job queue (Celery/Redis) — not a synchronous HTTP call.

### Anti-Pattern 5: Parallel Browser Contexts Without Rate Limits
**What:** Launch one Playwright context per portal simultaneously (63 concurrent browsers).
**Why bad:** Each Chromium context uses ~200MB RAM. 63 concurrent = ~12GB RAM minimum. Government portals may IP-ban aggressive crawlers. EC2 instance will OOM.
**Instead:** Pool browser contexts (max 5-10 concurrent). Implement per-portal delays (1-3 seconds between page loads). Respect robots.txt where present.

### Anti-Pattern 6: Storing Raw HTML as Primary Data
**What:** Dump raw HTML to the DB, parse at query time.
**Why bad:** Raw HTML from 5K listings is gigabytes of storage. Query-time parsing is slow and non-indexable.
**Instead:** Extract structured fields at scrape time. Store `raw_text` (plain text, not HTML) only as a debugging reference. All queryable data is in typed columns.

---

## Integration Points

| Integration | Direction | Protocol | Notes |
|-------------|-----------|----------|-------|
| Scraper → LLM API | Outbound | HTTPS REST | OpenAI/Anthropic/Google for Browser Use decisions + LangExtract extraction. Budget: ~$0.002/listing at gpt-4o-mini scale |
| Scraper → Embedding API | Outbound | HTTPS REST | text-embedding-3-small: ~$0.00002/1K tokens. Batch requests where possible |
| Scraper → PostgreSQL | Internal | TCP (Docker network) | Direct connection; no connection pooler needed at this scale |
| Next.js → PostgreSQL | Internal | TCP (Docker network) | Use Drizzle ORM with connection pool (max 10 connections) |
| Nginx → Next.js | Internal | HTTP | Reverse proxy on Docker bridge network |
| User Browser → Nginx | External | HTTPS (443) | TLS terminated at Nginx |
| Terraform → AWS API | Outbound | HTTPS | One-time infra provisioning; not runtime |

---

## Sources

- Browser Use architecture: [GitHub - browser-use/browser-use](https://github.com/browser-use/browser-use), [Browser-Use AI Agent Overview](https://www.labellerr.com/blog/browser-use-agent/)
- LangExtract pipeline: [GitHub - google/langextract](https://github.com/google/langextract), [LangExtract Deep Dive](https://towardsdatascience.com/extracting-structured-data-with-langextract-a-deep-dive-into-llm-orchestrated-workflows/)
- pgvector hybrid search: [Hybrid Search Missing Manual - ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual), [Hybrid Search Postgres - Jonathan Katz](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)
- HNSW indexing: [pgvector GitHub](https://github.com/pgvector/pgvector)
- Docker Compose scheduling: [Ofelia GitHub](https://github.com/mcuadros/ofelia), [Adding Cron Jobs to Docker Compose](https://distr.sh/blog/docker-compose-cron-jobs/)
- Next.js backend architecture: [Modern Full Stack Next.js 15+](https://softwaremill.com/modern-full-stack-application-architecture-using-next-js-15/)
- Scraping best practices: [Web Scraping Challenges 2025 - ScrapingBee](https://www.scrapingbee.com/blog/web-scraping-challenges/)
- RRF hybrid search implementation: [Building Hybrid Search RRF - DEV Community](https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk)
