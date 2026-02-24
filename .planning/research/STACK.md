# Technology Stack

**Project:** Procurement Intelligence Platform
**Domain:** Procurement monitoring / web scraping + semantic search
**Researched:** 2026-02-24
**Overall confidence:** HIGH (core stack is prescribed; libraries verified against official sources)

---

## Recommended Stack

### Runtime and Language Versions

| Layer | Technology | Version | Notes |
|-------|------------|---------|-------|
| Scraper runtime | Python | 3.11+ | Required by browser-use; 3.12 recommended |
| Frontend runtime | Node.js | 20.9+ (LTS) | Required by Next.js 16 |
| TypeScript | TypeScript | 5.1+ | Required by Next.js 16 |

---

### Core Framework: Scraper Pipeline (Python)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| browser-use | 0.11.12 | AI-driven browser automation | Prescribed. Combines vision + HTML extraction; handles diverse portal layouts without per-site scrapers. LangChain-compatible, MIT licensed. |
| Playwright (Python) | 1.58.0 | Headless browser rendering | browser-use dependency; best async browser automation in Python 2025. Auto-waits, reduces flakiness vs Selenium. |
| LangExtract | 1.1.1 | Structured field extraction from page text | Prescribed. Google-backed library; source-grounded extraction with schema enforcement via Controlled Generation. Supports Gemini (default), OpenAI, Ollama. |
| FastAPI | 0.133.0 | Internal API between scraper results and frontend | Industry-standard async Python web framework. Async-first, Pydantic-native, auto-generates OpenAPI docs. Use for `/api/` endpoints consumed by Next.js frontend. |
| SQLAlchemy | 2.0.46 | ORM for database access | Standard Python ORM for PostgreSQL. Async engine (via asyncpg) eliminates blocking. Use declarative mapping style from 2.0. |
| asyncpg | 0.31.0 | PostgreSQL async driver | 5x faster than psycopg3 in benchmarks; binary protocol; zero dependencies; native asyncio. Required for SQLAlchemy async engine. |
| Alembic | 1.14+ | Database migrations | De facto standard for SQLAlchemy migrations. Autogenerate diffs from models; run with sync engine even in async app. |
| Pydantic | 2.12.5 | Data validation and schemas | Native to FastAPI; 17x faster than v1 (Rust core); strict mode for scraping output validation. |
| APScheduler | 3.x | Nightly job scheduling | Lightweight in-process scheduler. No broker needed (unlike Celery). Sufficient for single nightly batch. See scheduling decision below. |
| uv | latest | Python package manager | 10-100x faster than pip; Rust-based; replaces pip+virtualenv+pyproject.toml management. browser-use's own docs use uv. |

**Scheduling decision — APScheduler over Celery:**
Celery requires a Redis/RabbitMQ broker (extra Docker service, extra complexity). For a single nightly batch at 2AM across 63 portals, APScheduler running inside the scraper container handles this cleanly. If concurrency grows beyond one machine, revisit Celery then.

**LangExtract LLM choice:**
LangExtract defaults to Gemini. For this platform, use `langextract[openai]` with `gpt-4o-mini` for cost efficiency — OpenAI is already needed for embeddings, so a single API key covers both. Alternatively, Gemini Flash is cheaper and well-supported; either works.

---

### Core Framework: Frontend (TypeScript/Next.js)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Next.js | 16.x (16.1.6) | Full-stack React framework | Prescribed. Latest stable major. App Router + Server Components is the correct model for data-heavy dashboards. Turbopack is now default bundler (2-5x faster builds). |
| React | 19.2 | UI library | Ships with Next.js 16. View Transitions, Activity, and useEffectEvent now stable. |
| Auth.js (NextAuth) | v5 | Credentials-based authentication | Standard for Next.js credential auth. Minimal setup for simple username/password login. JWT sessions; no DB persistence required. Compatible with Next.js 16 (proxy.ts replaces middleware.ts). |
| TanStack Table | v8 | Data table with sort/filter/pagination | Powers shadcn/ui Data Table component. Server-side pagination and filtering built in. Best React table library in 2025. |
| shadcn/ui | latest | Component library | Not a dependency — copy-paste components built on Radix UI + Tailwind. No lock-in. Data Table, Dialog, Input, Select, Badge, Command all available. |
| Tailwind CSS | v4 | Utility CSS | Ships with Next.js 16 create-next-app template. No configuration overhead. |
| TanStack Query | v5 | Client-side data fetching state | For client components that need search/filter interactivity with background refresh. Works with Next.js 16 Server Components via hydration. |

**Next.js 16 note:** Next.js 16 introduced breaking changes from 15. Key ones for this project: `params` and `searchParams` are now async; `cookies()`/`headers()` are async; `middleware.ts` renamed to `proxy.ts`. All mandatory — no compat shim in 16. If the team is more comfortable starting on 15.5 (still supported), that is a valid choice. Recommend 16 for greenfield.

---

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 17 | Primary data store | Prescribed. Docker image: `pgvector/pgvector:pg17`. Native full-text search (tsvector/tsquery) eliminates Elasticsearch for keyword search. |
| pgvector | 0.8.1 | Vector similarity search | Prescribed. Enables semantic search without a separate vector database. HNSW index for ANN search. 1,536-dimension vectors (OpenAI ada-compatible) well within 2,000-dimension limit. |
| OpenAI Embeddings API | text-embedding-3-small | Generate listing embeddings | $0.00002/1K tokens. 44% multilingual benchmark improvement over ada-002. 1,536 dimensions by default, reducible. For 5,000 listings/night, cost is negligible. |

**Hybrid search approach:**
Use PostgreSQL tsvector for keyword/filter queries ("IT consulting", NAICS code filtering, date ranges) and pgvector cosine similarity for natural language queries ("construction contracts expiring next month in Ontario"). Combine with a weighted rank merge (RRF — Reciprocal Rank Fusion) at the API layer. No Elasticsearch needed.

---

### Infrastructure and Deployment

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker | latest stable | Container runtime | Prescribed. All services containerized. |
| Docker Compose | v2.x | Multi-container orchestration | Prescribed. Single EC2 host; Compose manages all services with health checks. |
| Terraform | 1.x | Infrastructure-as-code | Prescribed. Manages EC2, Security Groups, EBS, Route53, IAM in ca-central-1. |
| AWS EC2 | t3.medium or t3.large | Application host | Prescribed. ca-central-1 for Canadian data sovereignty. t3.medium (2 vCPU, 4GB) baseline; t3.large (2 vCPU, 8GB) recommended — Playwright browser contexts consume ~50-100MB RAM each. |
| AWS EBS | gp3 100GB+ | Persistent storage | Attach to EC2 for PostgreSQL data volume. gp3 is cheaper and faster than gp2. |
| Nginx | alpine | Reverse proxy | Sits in front of Next.js (port 3000) and FastAPI (port 8000). Handles HTTPS termination, routes `/api/` to FastAPI. |
| Let's Encrypt / Certbot | latest | TLS certificates | Free certificates for procurement.eliastools.com. Certbot container handles renewal. |

---

### Supporting Libraries

#### Python Scraper

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ | HTTP client for API-style portals | Some of the 63 portals may expose REST/JSON endpoints; skip Playwright for those. |
| tenacity | 8.x | Retry logic with exponential backoff | Wrap all scraping calls. Rate limit (429) and transient failures are inevitable across 63 portals. |
| python-dotenv | 1.x | Environment variable loading | Local dev only; in Docker, use `env_file` in Compose. |
| structlog | 24.x | Structured JSON logging | Parse logs from EC2 easily; structured format compatible with CloudWatch Logs. |
| pytest + pytest-asyncio | latest | Testing | Async test support for FastAPI and scraper pipeline. |
| Alembic | 1.14+ | DB migrations | Run via separate Docker service or `docker compose run` on deploy. |

#### TypeScript Frontend

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Zod | 3.x | Runtime schema validation | Validate API responses from FastAPI in frontend. Pairs with TypeScript types. |
| nuqs | 2.x | URL search param state | Sync filter state (category, date range, region) to URL. Enables shareable search links and browser back/forward. |
| date-fns | 3.x | Date formatting | Format posting/closing dates in listings table. Lightweight vs moment.js. |
| react-hook-form | 7.x | Form handling | Login form and any filter forms. Minimal re-renders. |

---

## Docker Compose Service Map

```
services:
  db:          pgvector/pgvector:pg17  — PostgreSQL 17 + pgvector
  scraper:     python:3.12             — FastAPI + APScheduler + browser-use pipeline
  frontend:    node:20-alpine          — Next.js 16 production build
  nginx:       nginx:alpine            — Reverse proxy + TLS termination
  certbot:     certbot/certbot         — Let's Encrypt certificate renewal
```

Scraper container runs both the FastAPI API server and the APScheduler nightly job. If these need to separate later, split into `api` and `worker` services — trivial with Compose.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Scheduling | APScheduler | Celery + Redis | Celery requires a broker (Redis/RabbitMQ = extra container, extra ops). Overkill for one nightly job. APScheduler runs in-process; simpler. |
| Scheduling | APScheduler | cron (Docker cron) | Cron in Docker requires a separate cron container or `cron` inside the scraper image. Harder to share Python context, logging, and error handling with the app. APScheduler integrates cleanly. |
| Auth | Auth.js v5 (credentials) | Lucia | Both work. Auth.js is more mature, better documented for Next.js. Lucia is fine for greenfield but smaller community. |
| Auth | Auth.js v5 | Roll-your-own JWT | Don't. JWT rotation, session invalidation, and CSRF are subtle. Auth.js handles them. |
| Search | PostgreSQL FTS + pgvector | Elasticsearch | Elasticsearch = separate service, significant ops overhead, licensing cost (non-OSS for advanced features). pgvector is "good enough" for 5,000 listings. |
| Search | PostgreSQL FTS + pgvector | Typesense | Typesense is excellent for keyword search but lacks native semantic/vector search. Would need pgvector alongside it anyway. |
| ORM | SQLAlchemy 2.0 async | SQLModel | SQLModel is built on SQLAlchemy but abstracts too much for complex queries (pgvector cosine operators, tsvector). Stick with SQLAlchemy directly. |
| Embeddings | OpenAI text-embedding-3-small | Cohere embed-v4 | OpenAI is simpler if already using GPT for LangExtract. Cohere is cheaper at scale but adds a second vendor. Start with OpenAI. |
| Package manager | uv | Poetry | uv is 10-100x faster; browser-use itself recommends uv. Both use pyproject.toml. Migrate to uv. |
| Next.js version | 16.x | 15.5 | 16 is stable (released Oct 2025). Turbopack default, better caching, React 19.2. No reason to start on 15 for a greenfield project. |
| Frontend | Next.js 16 | Remix | Remix is solid but smaller ecosystem, fewer shadcn/ui examples. Next.js is the dominant choice in 2025 for this type of internal tool. |

---

## What NOT to Use

| Technology | Why Avoid |
|------------|-----------|
| Scrapy | Designed for traditional HTML scraping. Cannot drive JavaScript-rendered portals (most of the 63 targets). Would require Splash or Selenium integration, defeating the purpose. Use Playwright + browser-use instead. |
| Selenium | Slower than Playwright; no async API; no built-in AI integration. Playwright supersedes it entirely. |
| BeautifulSoup alone | Insufficient for JS-rendered portals. Fine as a helper for parsing raw HTML after Playwright captures it, but not as primary extraction tool when LangExtract is already doing this. |
| Celery (for this use case) | Celery requires Redis or RabbitMQ broker — an extra container with no benefit for a single nightly batch. APScheduler is sufficient. |
| Elasticsearch / OpenSearch | Operational overhead (separate service, JVM, memory). PostgreSQL FTS + pgvector covers this use case at 5K listings/night. |
| Prisma (Python) | Prisma's Python client is experimental/unstable. SQLAlchemy 2.0 is production-grade. |
| SQLite | Not suitable for concurrent access from scraper + API + scheduled jobs. PostgreSQL is the right choice. |
| Redux / Zustand | Heavy client state management is unnecessary. Next.js Server Components handle most data fetching. TanStack Query handles client-side search state. |
| moment.js | Deprecated in 2020. Use date-fns or native Intl. |
| Pages Router (Next.js) | Legacy. App Router is the current model. All new Next.js development should use App Router. |
| Next.js 14 or older | Two major versions behind. Missing Turbopack stability, async params API, and React 19.2. |

---

## Installation

### Python Scraper

```bash
# Install uv (Rust-based package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init procurement-scraper
cd procurement-scraper

# Core dependencies
uv add browser-use playwright langextract[openai] fastapi[standard] \
       sqlalchemy[asyncio] asyncpg alembic pydantic apscheduler \
       httpx tenacity structlog python-dotenv

# Install Playwright browsers
uvx playwright install chromium

# Dev dependencies
uv add --dev pytest pytest-asyncio httpx
```

### Frontend

```bash
# Create Next.js 16 project
npx create-next-app@latest procurement-dashboard \
  --typescript --tailwind --eslint --app --src-dir

cd procurement-dashboard

# Additional dependencies
npm install @auth/core next-auth @tanstack/react-table @tanstack/react-query \
            zod nuqs date-fns react-hook-form

# shadcn/ui setup (copy-paste components, not a package)
npx shadcn@latest init
# Then add components as needed:
npx shadcn@latest add table input select badge command dialog
```

### Docker Compose (reference snippet)

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: procurement
      POSTGRES_USER: procurement
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U procurement"]
      interval: 10s
      timeout: 5s
      retries: 5

  scraper:
    build: ./scraper
    depends_on:
      db:
        condition: service_healthy
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://procurement:${DB_PASSWORD}@db:5432/procurement

  frontend:
    build: ./frontend
    depends_on:
      - scraper
    environment:
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      API_BASE_URL: http://scraper:8000

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - certbot-etc:/etc/letsencrypt
    depends_on:
      - frontend
      - scraper

  certbot:
    image: certbot/certbot
    volumes:
      - certbot-etc:/etc/letsencrypt

volumes:
  pgdata:
  certbot-etc:
```

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| browser-use version | HIGH | Verified on PyPI: 0.11.12 (released 2026-02-23) |
| LangExtract version | HIGH | Verified on PyPI: 1.1.1 (released 2025-11-27); official Google library |
| Playwright Python version | HIGH | PyPI: 1.58.0 (released 2026-01-30) |
| FastAPI version | HIGH | PyPI: 0.133.0 (released 2026-02-24) |
| SQLAlchemy version | HIGH | Official blog: 2.0.46 (released 2026-01-21) |
| asyncpg version | HIGH | PyPI: 0.31.0 (released 2025-11-24) |
| pgvector version | HIGH | GitHub: v0.8.1; pgvector/pgvector:pg17 Docker image confirmed |
| PostgreSQL version | HIGH | pgvector/pgvector:pg17 is the canonical Docker image |
| Next.js version | HIGH | Next.js 16 stable (released 2025-10-21); 16.1.6 current patch |
| Auth.js v5 compatibility | HIGH | Confirmed compatible with Next.js 16; proxy.ts rename applies |
| APScheduler over Celery | MEDIUM | Reasoned from architecture constraints; no specific benchmark for this pattern |
| OpenAI text-embedding-3-small | HIGH | Official OpenAI docs; pricing and dimensions verified |
| Hybrid search (FTS + pgvector) | MEDIUM | Pattern is documented; RRF merging at application layer is a known pattern but implementation detail is left to phase research |
| Terraform + EC2 ca-central-1 | HIGH | Standard pattern; region is a config parameter; no special constraints in ca-central-1 |

---

## Key Risks and Phase Flags

1. **browser-use + headless Chromium on EC2** — Playwright with browser-use needs a display or Xvfb unless using `--no-sandbox` in headless mode. The EC2 instance must have sufficient memory (8GB+) to run multiple concurrent Chromium contexts during the nightly scrape. Flag for Phase: Scraper Build.

2. **LangExtract LLM API costs** — Each portal page extraction is an LLM call. At 63 portals with ~20-80 listings per portal, estimate 63-5,040 extraction calls per night. Budget/rate-limit accordingly. Gemini Flash is cheaper than GPT-4o for extraction; evaluate in early phases.

3. **pgvector 2,000-dimension limit for HNSW indexing** — text-embedding-3-small produces 1,536 dimensions by default, within the limit. Do not switch to text-embedding-3-large (3,072 dims) without switching to halfvec type or removing HNSW index.

4. **Next.js 16 async params** — All route params, cookies(), and headers() are now async. This is a source of runtime errors if overlooked. Enforce TypeScript strict mode from day one.

5. **Auth.js v5 + proxy.ts** — middleware.ts is deprecated in Next.js 16; use proxy.ts. Credentials provider uses JWT sessions (no DB required). Simple for an internal team.

---

## Sources

- browser-use PyPI: https://pypi.org/project/browser-use/
- browser-use GitHub: https://github.com/browser-use/browser-use
- LangExtract PyPI: https://pypi.org/project/langextract/
- LangExtract GitHub: https://github.com/google/langextract
- LangExtract Google Blog announcement: https://developers.googleblog.com/introducing-langextract-a-gemini-powered-information-extraction-library/
- Playwright Python PyPI: https://pypi.org/project/playwright/
- FastAPI PyPI: https://pypi.org/project/fastapi/
- FastAPI Docker deployment: https://fastapi.tiangolo.com/deployment/docker/
- SQLAlchemy 2.0.46 release: https://www.sqlalchemy.org/blog/2026/01/21/sqlalchemy-2.0.46-released/
- asyncpg PyPI: https://pypi.org/project/asyncpg/
- pgvector GitHub: https://github.com/pgvector/pgvector
- pgvector Docker Hub: https://hub.docker.com/r/pgvector/pgvector
- Next.js 16 release blog: https://nextjs.org/blog/next-16
- Next.js 16 upgrade guide: https://nextjs.org/docs/app/guides/upgrading/version-16
- Auth.js v5 credentials: https://authjs.dev/getting-started/providers/credentials
- OpenAI embeddings models: https://platform.openai.com/docs/models
- APScheduler vs Celery: https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat
- shadcn/ui Data Table: https://ui.shadcn.com/docs/components/radix/data-table
- TanStack Query: https://tanstack.com/query/latest
- PostgreSQL hybrid search: https://www.tigerdata.com/blog/combining-semantic-search-and-full-text-search-in-postgresql-with-cohere-pgvector-and-pgai
- Terraform EC2 Docker Compose: https://klotzandrew.com/blog/deploy-an-ec2-to-run-docker-with-terraform/
- Pydantic v2: https://docs.pydantic.dev/latest/
