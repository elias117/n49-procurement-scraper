# Procurement Intelligence Platform

Monitors 60+ Canadian government procurement portals nightly, surfaces translation-related tenders via hybrid keyword + semantic search, and delivers results through a web dashboard.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌────────────┐
│   Scraper    │────▶│ PostgreSQL  │◀────│  FastAPI    │
│  (Playwright)│     │  + pgvector │     │   (API)     │
└─────────────┘     └─────────────┘     └────────────┘
                                              ▲
                                              │
                    ┌─────────────┐     ┌─────┴──────┐
                    │    Nginx    │◀────│   Next.js   │
                    │ (TLS proxy) │     │    (Web)    │
                    └─────────────┘     └────────────┘
```

**Scraper** — Playwright-based deterministic parsers (no LLM in the pipeline). Handles BidsAndTenders, SEAO, CanadaBuys, MERX, BC Bid, SaskTenders, NBON, APC, Ariba, and tier-3 municipal portals. Runs inside Xvfb (non-headless) because procurement portals 403-block headless browsers.

**API** — FastAPI with hybrid search (tsvector keyword + pgvector cosine similarity, merged via Reciprocal Rank Fusion). Filters by region, portal, date range, contract value, and classification codes.

**Web** — Next.js 14 with NextAuth, search dashboard, listing detail, and portal health monitoring.

**Database** — PostgreSQL 17 with pgvector for 1536-dim OpenAI embeddings and pgcrypto for user auth.

## Stack

| Component | Technology |
|-----------|-----------|
| Scraper | Python 3.11, Playwright, Xvfb |
| API | FastAPI, psycopg2, uvicorn |
| Web | Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui |
| Database | PostgreSQL 17 + pgvector |
| Proxy | Nginx (TLS termination, Let's Encrypt) |
| CI/CD | GitHub Actions (test → deploy to EC2 via SSH) |
| Hosting | AWS EC2 (ca-central-1), Docker Compose |

## Quick Start

```bash
# 1. Clone
git clone git@github.com:elias117/n49-procurement-scraper.git
cd n49-procurement-scraper

# 2. Configure
cp .env.example .env
# Edit .env with real credentials

# 3. Start services
docker compose up -d

# 4. Run scraper manually (or wait for cron)
docker exec procurement-intel-scraper-1 python scraper/main.py
```

The API serves at `http://localhost:8000`, the web dashboard at `http://localhost:3000`.

## Project Structure

```
├── api/                    # FastAPI search + listing API
│   ├── routers/            # health, search, listings, portal_health, users
│   ├── search/             # hybrid search engine (RRF, embeddings, facets)
│   ├── models/             # request/response schemas
│   └── tests/              # pytest unit tests
├── scraper/                # Playwright scraper pipeline
│   ├── pipeline/           # per-portal scrapers + orchestrator
│   │   └── tier3/          # municipal portal scrapers
│   └── tests/              # pytest unit tests
├── web/                    # Next.js frontend
│   └── src/
│       ├── app/            # pages (dashboard, login, health)
│       └── components/     # search UI, health monitoring
├── db/migrations/          # SQL migration files (run on first start)
├── nginx/                  # Nginx reverse proxy config
├── docker-compose.yml      # Development stack
├── docker-compose.prod.yml # Production overlay
└── keywords_library.csv    # 56 keyword rules across categories
```

## Portal Coverage

63 portals across federal, provincial, and municipal levels:

- **BidsAndTenders** — 29 portals (Ontario municipalities, NS, PEI, etc.)
- **SEAO** — 9 Québec public procurement portals
- **CanadaBuys** — Federal procurement (RSS/CSV ingest)
- **MERX** — National commercial marketplace
- **BC Bid, SaskTenders, NBON, APC** — Provincial portals
- **Ariba** — Edmonton, Nova Scotia, Toronto
- **Tier 3** — Montréal, Vancouver, Windsor municipal portals

## Search Modes

| Mode | Description |
|------|-------------|
| `hybrid` (default) | Keyword (tsvector) + semantic (pgvector cosine) merged via RRF |
| `exact` | ILIKE pattern matching on title, description, reference number |
| Browse | No query — returns all open listings with filters/sort |

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | For embedding generation (text-embedding-3-small) |
| `NEXTAUTH_SECRET` | NextAuth session encryption |

## Tests

```bash
# Run all tests (354 tests across scraper + API)
python -m pytest scraper/tests/ api/tests/ -q

# Run with coverage
python -m pytest scraper/tests/ api/tests/ --cov=scraper --cov=api
```

CI runs tests automatically on every push to main before deploying.

## Deployment

Production runs on AWS EC2 (ca-central-1) via Docker Compose with the prod overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

CI/CD is handled by `.github/workflows/deploy.yml` — pushes to main trigger tests, then SSH deploy to EC2.

## License

Private — n49 Systems.
