---
phase: 1-infrastructure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker-compose.yml
  - .env.example
  - .gitignore
  - db/migrations/001_initial_schema.sql
  - db/migrations/002_seed_portals.sql
  - scraper/Dockerfile
  - scraper/main.py
  - web/Dockerfile
  - web/package.json
  - web/server.js
  - nginx/nginx.conf
  - terraform/main.tf
  - terraform/variables.tf
  - terraform/outputs.tf
  - terraform/user_data.sh
autonomous: false
requirements:
  - INFR-01
  - INFR-02
  - INFR-03
  - INFR-04

must_haves:
  truths:
    - "docker compose up starts all 4 services (db, scraper, web, nginx) without errors on EC2"
    - "PostgreSQL schema contains listings, portals, and scrape_runs tables with all specified columns, indexes, and constraints"
    - "63 portals are seeded in the portals table with correct metadata (level, province, language, requires_login, enabled)"
    - "HNSW index exists on listings.embedding column before any data is inserted"
    - "tsvector GIN index exists for full-text search on title + description"
    - "(source_portal, source_listing_id) composite unique constraint exists on listings table"
    - "All date/time columns use TIMESTAMPTZ, not TIMESTAMP"
    - "terraform plan shows no drift after terraform apply in ca-central-1"
    - "HTTPS resolves at procurement.eliastools.com with valid Let's Encrypt certificate"
    - "HTTP requests to procurement.eliastools.com redirect to HTTPS"
  artifacts:
    - path: "docker-compose.yml"
      provides: "All service definitions with health checks, volumes, networks"
    - path: "db/migrations/001_initial_schema.sql"
      provides: "Complete schema for listings, portals, scrape_runs with all indexes"
    - path: "db/migrations/002_seed_portals.sql"
      provides: "INSERT statements for all 63 portals"
    - path: "terraform/main.tf"
      provides: "VPC, subnet, EC2, security groups, Route53, key pair"
    - path: "nginx/nginx.conf"
      provides: "Reverse proxy config with TLS termination"
    - path: "scraper/Dockerfile"
      provides: "Playwright-based Python container stub"
    - path: "web/Dockerfile"
      provides: "Node.js container stub serving port 3000"
  key_links:
    - from: "docker-compose.yml"
      to: "db/migrations/*.sql"
      via: "volume mount runs migrations on startup"
      pattern: "volumes.*db/migrations"
    - from: "nginx/nginx.conf"
      to: "web service"
      via: "proxy_pass to web:3000"
      pattern: "proxy_pass.*web:3000"
    - from: "terraform/main.tf"
      to: "EC2 instance"
      via: "user_data script installs Docker and clones repo"
      pattern: "user_data"
    - from: "docker-compose.yml"
      to: ".env"
      via: "env_file directive loads secrets"
      pattern: "env_file"
---

<objective>
Provision the complete infrastructure for the Procurement Intelligence Platform: Terraform creates an EC2 instance in ca-central-1 with all networking, Docker Compose runs PostgreSQL+pgvector, scraper stub, Next.js stub, and Nginx on the instance, PostgreSQL has the full schema with all tables/indexes/constraints and 63 seeded portals, and Nginx terminates TLS with a Let's Encrypt certificate for procurement.eliastools.com.

Purpose: This is the foundation everything else builds on. No scraper, no search, no UI can be built without the database schema and running infrastructure.

Output: Working EC2 instance at procurement.eliastools.com with all services running via Docker Compose, PostgreSQL schema ready to receive data.
</objective>

<execution_context>
This plan has 5 tasks executed sequentially. Tasks 1-3 create all local files and verify with docker compose. Task 4 provisions AWS infrastructure. Task 5 deploys everything to EC2 and sets up TLS.
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/1/1-CONTEXT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create project scaffold with Docker Compose, service stubs, and Nginx config</name>
  <files>
    docker-compose.yml
    .env.example
    .gitignore
    scraper/Dockerfile
    scraper/main.py
    scraper/requirements.txt
    web/Dockerfile
    web/package.json
    web/server.js
    nginx/nginx.conf
  </files>
  <action>
Create the project scaffold — Docker Compose, service stubs, and Nginx config. The PostgreSQL schema migration is created in Task 2. All files described below should be created exactly as specified.

**1. `.gitignore`** — Add these entries (append if file exists):
```
# Terraform
terraform/.terraform/
terraform/terraform.tfstate
terraform/terraform.tfstate.backup
terraform/*.tfvars
*.tfstate
*.tfstate.backup

# Environment secrets
.env
*.pem

# Docker
postgres_data/

# Node
node_modules/

# Python
__pycache__/
*.pyc
.venv/
```

**2. `.env.example`** — Template for required environment variables (NO real secrets):
```
# PostgreSQL
POSTGRES_DB=procurement
POSTGRES_USER=procurement
POSTGRES_PASSWORD=changeme_use_strong_password

# Database URL (for application services)
DATABASE_URL=postgresql://procurement:changeme_use_strong_password@db:5432/procurement

# OpenAI (for future phases - scraper embedding)
OPENAI_API_KEY=sk-your-key-here

# NextAuth (for future phases - web auth)
NEXTAUTH_SECRET=changeme_generate_with_openssl_rand_base64_32
```

**3. `docker-compose.yml`** — Define all 4 services. CRITICAL details:
- Use `pgvector/pgvector:pg17` image for db (NOT plain postgres)
- Scraper uses Playwright base image `mcr.microsoft.com/playwright/python:v1.51.0-noble` (Pitfall 11 prevention)
- Scraper gets `shm_size: '2gb'` (Pitfall 3 prevention)
- Scraper gets `mem_limit: 4g` (Pitfall 3 prevention)
- PostgreSQL binds ONLY to Docker network, NOT exposed on host ports (Security)
- Nginx exposes ports 80 and 443
- Web service exposes port 3000 internally only
- All services use `env_file: .env`
- PostgreSQL has healthcheck using `pg_isready`
- DB migrations run automatically via volume mount of `./db/migrations` to `/docker-entrypoint-initdb.d/` (PostgreSQL runs .sql files in this dir on first start, in alphabetical order)
- Named volume `postgres_data` for database persistence
- Named volume `certbot_etc` for Let's Encrypt certificates
- Named volume `certbot_var` for certbot working directory
- Mount `./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro` for nginx config

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    restart: unless-stopped
    env_file: .env
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U procurement -d procurement"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  scraper:
    build: ./scraper
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    shm_size: '2gb'
    mem_limit: 4g
    networks:
      - internal

  web:
    build: ./web
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "3000"
    networks:
      - internal

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - certbot_etc:/etc/letsencrypt
      - certbot_var:/var/www/certbot
    depends_on:
      - web
    networks:
      - internal

volumes:
  postgres_data:
  certbot_etc:
  certbot_var:

networks:
  internal:
    driver: bridge
```

**4. `scraper/Dockerfile`** — Stub scraper container using Playwright base image (Pitfall 11):
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.51.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Stub: just keep the container running for Phase 1
CMD ["python", "main.py"]
```

**5. `scraper/requirements.txt`** — Minimal deps for stub:
```
# Phase 1: stub only. Full dependencies added in Phase 2.
psycopg2-binary==2.9.10
```

**6. `scraper/main.py`** — Stub that logs readiness and sleeps:
```python
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper")

if __name__ == "__main__":
    logger.info("Scraper container started (Phase 1 stub)")
    logger.info("Scraper pipeline will be implemented in Phase 2")
    # Keep container running so Docker Compose doesn't restart it
    while True:
        time.sleep(3600)
```

**7. `web/Dockerfile`** — Stub Node.js web server:
```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

EXPOSE 3000

CMD ["node", "server.js"]
```

**8. `web/package.json`** — Minimal package.json for stub:
```json
{
  "name": "procurement-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.21.0"
  }
}
```

**9. `web/server.js`** — Stub Express server returning health check:
```javascript
const express = require('express');
const app = express();
const PORT = 3000;

app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    service: 'procurement-web',
    phase: 1,
    message: 'Next.js application will be implemented in Phase 4'
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Web stub listening on port ${PORT}`);
});
```

**10. `nginx/nginx.conf`** — Initial HTTP-only config (TLS added in Task 4 after certbot runs). This config serves HTTP and the certbot challenge, but does NOT yet have SSL:
```nginx
server {
    listen 80;
    server_name procurement.eliastools.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://web:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

After creating all files, copy `.env.example` to `.env` and set a real password for local testing. Then run `docker compose up --build -d` and verify all 4 services start. Check with `docker compose ps` — all should show "running" or "Up".

Note: The PostgreSQL schema migration (001_initial_schema.sql) is created in Task 2. At this point the db container starts but has no application tables yet — just verify it's healthy.

Then `docker compose down` to clean up.
  </action>
  <verify>
    <automated>
    cd /Users/clawbot/dev && cp .env.example .env && docker compose up --build -d && sleep 15 && docker compose ps --format "table {{.Name}}\t{{.Status}}" && curl -sf http://localhost:80/ && docker compose down
    </automated>
    <manual>All 4 services (db, scraper, web, nginx) show "Up" status. Nginx proxies to web stub successfully.</manual>
  </verify>
  <done>
    - docker compose up starts all 4 services without errors
    - db (pgvector/pgvector:pg17) is healthy
    - scraper container runs stub process
    - web container serves health check on port 3000
    - nginx proxies port 80 to web service
    - .env.example has all required variables
    - .gitignore covers terraform state, .env, *.pem
  </done>
</task>

<task type="auto">
  <name>Task 2: Create PostgreSQL schema migration with all tables, indexes, and constraints</name>
  <files>
    db/migrations/001_initial_schema.sql
  </files>
  <action>
Create the complete PostgreSQL schema migration at `db/migrations/001_initial_schema.sql`. This is the most critical file in Phase 1 — every column, index, and constraint must match the specification exactly.

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- PORTALS TABLE
-- Registry of all procurement portals being monitored
-- ============================================================
CREATE TABLE portals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    url             TEXT NOT NULL,
    level           VARCHAR(20) NOT NULL CHECK (level IN ('federal', 'provincial', 'municipal')),
    province        VARCHAR(50),          -- NULL for federal portals
    language        VARCHAR(10) NOT NULL CHECK (language IN ('en', 'fr', 'both')),
    requires_login  BOOLEAN NOT NULL DEFAULT false,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- LISTINGS TABLE
-- Core procurement listing data extracted from portals
-- ============================================================
CREATE TABLE listings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification (upsert key)
    source_portal       UUID NOT NULL REFERENCES portals(id),
    source_listing_id   VARCHAR(500) NOT NULL,

    -- Core fields
    title               TEXT NOT NULL,
    description         TEXT,
    status              VARCHAR(20) NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'closed', 'cancelled', 'awarded')),
    language            VARCHAR(10),

    -- Dates (ALL TIMESTAMPTZ per Pitfall 6)
    posting_date        TIMESTAMPTZ,
    closing_date        TIMESTAMPTZ,
    amended_date        TIMESTAMPTZ,

    -- Location
    province            VARCHAR(50),       -- Province-level for filtering
    raw_location        TEXT,              -- Raw location string as-is from portal

    -- Classification codes (JSONB arrays - multiple codes per system)
    classification_codes JSONB DEFAULT '[]'::jsonb,
    -- Format: [{"system": "NAICS", "code": "541512", "description": "Computer Systems Design"}, ...]
    -- Supports NAICS, UNSPSC, GSIN

    -- Contract values
    value_min           NUMERIC,           -- Exact amount: same as value_max
    value_max           NUMERIC,           -- Range: different from value_min. Unknown: both NULL

    -- Contact info (variable structure)
    contact_info        JSONB,
    -- Format: {"name": "...", "email": "...", "phone": "..."} or array of contacts

    -- Document links
    documents           JSONB DEFAULT '[]'::jsonb,
    -- Format: [{"name": "RFP Document", "type": "RFP", "date": "2026-01-15", "url": "https://..."}]

    -- Amendment tracking (latest version only)
    revision            INTEGER NOT NULL DEFAULT 1,

    -- Source reference
    source_url          TEXT,

    -- Embedding for semantic search
    embedding           vector(1536),
    embedding_model     VARCHAR(100),      -- e.g., 'text-embedding-3-small'

    -- Timestamps (ALL TIMESTAMPTZ per Pitfall 6)
    last_scraped_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Composite unique constraint for upsert (Pitfall 7)
    UNIQUE (source_portal, source_listing_id)
);

-- Full-text search index (tsvector GIN index)
-- Covers title + description for keyword search
CREATE INDEX listings_fts_idx ON listings
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));

-- Vector similarity index (HNSW - created before data insertion per Pitfall 10)
-- m=16, ef_construction=64 sized for up to 50K listings
CREATE INDEX listings_embedding_idx ON listings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Performance indexes
CREATE INDEX listings_status_idx ON listings (status);
CREATE INDEX listings_closing_date_idx ON listings (closing_date);
CREATE INDEX listings_posting_date_idx ON listings (posting_date);
CREATE INDEX listings_province_idx ON listings (province);
CREATE INDEX listings_source_portal_idx ON listings (source_portal);

-- ============================================================
-- SCRAPE_RUNS TABLE
-- Per-portal audit trail for every scrape execution (Pitfall 13)
-- ============================================================
CREATE TABLE scrape_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal_id       UUID NOT NULL REFERENCES portals(id),
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed')),
    listings_found  INTEGER DEFAULT 0,
    listings_new    INTEGER DEFAULT 0,
    listings_updated INTEGER DEFAULT 0,
    error_message   TEXT,
    duration_seconds NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX scrape_runs_portal_idx ON scrape_runs (portal_id);
CREATE INDEX scrape_runs_started_at_idx ON scrape_runs (started_at);
```

After creating the file, reset the database to run the migration (PostgreSQL runs .sql files in /docker-entrypoint-initdb.d/ on first start only):
```bash
docker compose down -v  # Remove volumes to reset DB
docker compose up -d
sleep 15
docker compose exec db psql -U procurement -d procurement -c "\dt"
```
This should show tables: portals, listings, scrape_runs.

Verify indexes:
```bash
docker compose exec db psql -U procurement -d procurement -c "\di"
```
Should show: listings_fts_idx (gin), listings_embedding_idx (hnsw), and all performance indexes.

Verify the pgvector extension:
```bash
docker compose exec db psql -U procurement -d procurement -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```
  </action>
  <verify>
    <automated>
    cd /Users/clawbot/dev && docker compose down -v && docker compose up -d && sleep 15 && docker compose exec db psql -U procurement -d procurement -c "\dt" && docker compose exec db psql -U procurement -d procurement -c "\di" && docker compose exec db psql -U procurement -d procurement -c "SELECT extname FROM pg_extension WHERE extname = 'vector';" && docker compose exec db psql -U procurement -d procurement -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'listings' AND column_name IN ('posting_date', 'closing_date', 'created_at', 'updated_at', 'last_scraped_at', 'amended_date') ORDER BY column_name;" && docker compose down
    </automated>
    <manual>Tables portals, listings, scrape_runs exist. All date columns show "timestamp with time zone". HNSW and GIN indexes exist. pgvector extension is loaded.</manual>
  </verify>
  <done>
    - PostgreSQL has listings, portals, scrape_runs tables
    - All date/time columns are TIMESTAMPTZ
    - HNSW index exists on listings.embedding
    - GIN tsvector index exists for full-text search
    - (source_portal, source_listing_id) UNIQUE constraint exists
    - pgvector extension is loaded
    - classification_codes, contact_info, documents are JSONB
    - value_min and value_max are NUMERIC
    - status CHECK constraint covers open/closed/cancelled/awarded
  </done>
</task>

<task type="auto">
  <name>Task 3: Create portal seed migration with all 63 portals</name>
  <files>
    db/migrations/002_seed_portals.sql
  </files>
  <action>
Create the portal seed migration file `db/migrations/002_seed_portals.sql` that INSERTs all 63 portals.

The portals table has these columns: `id` (UUID, auto-generated), `name`, `url`, `level` (federal/provincial/municipal), `province` (nullable for federal), `language` (en/fr/both), `requires_login` (boolean), `enabled` (boolean).

Rule: Portals with `requires_login = true` get `enabled = false`.

The 63 portals consist of:
1. **Federal portals** (level='federal', province=NULL)
2. **Provincial portals** (level='provincial')
3. **Municipal portals** from municipalities.xlsx (level='municipal')

Here is the COMPLETE list of all 63 portals to seed. The executor MUST include every single one:

```sql
-- ============================================================
-- 002_seed_portals.sql
-- Seed all 63 procurement portals
-- ============================================================

-- =========================
-- FEDERAL PORTALS (2)
-- =========================
INSERT INTO portals (name, url, level, province, language, requires_login, enabled) VALUES
('CanadaBuys', 'https://canadabuys.canada.ca/en/tender-opportunities', 'federal', NULL, 'both', false, true),
('MERX', 'https://www.merx.com/', 'federal', NULL, 'both', true, false);

-- =========================
-- PROVINCIAL PORTALS (11)
-- =========================
INSERT INTO portals (name, url, level, province, language, requires_login, enabled) VALUES
('BC Bid', 'https://www.bcbid.gov.bc.ca/', 'provincial', 'British Columbia', 'en', false, true),
('Alberta Purchasing Connection', 'https://vendor.purchasingconnection.ca/', 'provincial', 'Alberta', 'en', true, false),
('SaskTenders', 'https://www.sasktenders.ca/', 'provincial', 'Saskatchewan', 'en', false, true),
('MERX Manitoba', 'https://www.merx.com/mbgov', 'provincial', 'Manitoba', 'en', true, false),
('Ontario Tenders Portal', 'https://ontariotenders.bidsandtenders.ca/', 'provincial', 'Ontario', 'en', false, true),
('SEAO', 'https://www.seao.ca/', 'provincial', 'Quebec', 'fr', true, false),
('New Brunswick Opportunities', 'https://www.gnb.ca/content/gnb/en/departments/finance/procurement.html', 'provincial', 'New Brunswick', 'both', false, true),
('Nova Scotia Procurement', 'https://procurement.novascotia.ca/', 'provincial', 'Nova Scotia', 'en', false, true),
('PEI Procurement', 'https://www.princeedwardisland.ca/en/topic/procurement', 'provincial', 'Prince Edward Island', 'en', false, true),
('Newfoundland Public Procurement', 'https://www.gov.nl.ca/ppa/', 'provincial', 'Newfoundland and Labrador', 'en', false, true),
('Northwest Territories Contract Registry', 'https://contracts.fin.gov.nt.ca/', 'provincial', 'Northwest Territories', 'en', false, true);

-- =========================
-- MUNICIPAL PORTALS (50)
-- =========================
INSERT INTO portals (name, url, level, province, language, requires_login, enabled) VALUES
('Toronto Bids Portal', 'https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/', 'municipal', 'Ontario', 'en', false, true),
('Montreal Tenders', 'https://montreal.ca/en/services/tenders-and-contracts', 'municipal', 'Quebec', 'both', false, true),
('Calgary MERX', 'https://www.calgary.merx.com/', 'municipal', 'Alberta', 'en', true, false),
('Edmonton Procurement', 'https://www.edmonton.ca/business_economy/selling_to_the_city/bid-procurement-opportunities', 'municipal', 'Alberta', 'en', true, false),
('Ottawa MERX', 'https://www.merx.com/cityofottawa', 'municipal', 'Ontario', 'en', true, false),
('Winnipeg MERX', 'https://www.merx.com/mbgov/cityofwinnipeg', 'municipal', 'Manitoba', 'en', true, false),
('Mississauga Bids', 'https://mississauga.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Vancouver Procurement', 'https://vancouver.ca/doing-business/bids-contracts-rfps-and-supplier-portal.aspx', 'municipal', 'British Columbia', 'en', false, true),
('Brampton Bids', 'https://brampton.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Hamilton Bids', 'https://hamilton.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Surrey Bids', 'https://surrey.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Quebec City Procurement', 'https://www.ville.quebec.qc.ca/en/gens_affaires/fournisseur/', 'municipal', 'Quebec', 'both', false, true),
('Halifax Bids', 'https://halifax.bidsandtenders.ca/', 'municipal', 'Nova Scotia', 'en', false, true),
('Laval SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('London Bids', 'https://london.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Markham Bids', 'https://markham.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Vaughan Bids', 'https://vaughan.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Gatineau SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Saskatoon Bids', 'https://saskatoon.bidsandtenders.ca/', 'municipal', 'Saskatchewan', 'en', false, true),
('Kitchener Bids', 'https://kitchener.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Longueuil SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Burnaby Bids', 'https://burnaby.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Windsor Procurement', 'https://www.citywindsor.ca/business/Bids-and-Tenders', 'municipal', 'Ontario', 'en', false, true),
('Regina SaskTenders', 'https://www.sasktenders.ca/', 'municipal', 'Saskatchewan', 'en', false, true),
('Richmond Bids', 'https://richmond.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Richmond Hill Bids', 'https://richmondhill.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Oakville Bids', 'https://oakville.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Burlington Bids', 'https://burlington.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Greater Sudbury Bids', 'https://greatersudbury.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Sherbrooke SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Oshawa Bids', 'https://oshawa.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Saguenay SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Levis SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('Barrie Bids', 'https://barrie.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Abbotsford Bids', 'https://abbotsford.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true),
('Coquitlam Procurement', 'https://www.coquitlam.ca/140/Bid-Opportunities', 'municipal', 'British Columbia', 'en', false, true),
('Trois-Rivieres SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('St. Catharines Bids', 'https://stcatharines.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Cambridge Procurement', 'https://www.cambridge.ca/en/build-invest-grow/Bids-and-Tenders.aspx', 'municipal', 'Ontario', 'en', false, true),
('Whitby Bids', 'https://whitby.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Guelph Bids', 'https://guelph.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Kingston Procurement', 'https://www.cityofkingston.ca/council-and-city-administration/procurement/', 'municipal', 'Ontario', 'en', false, true),
('Kelowna Procurement', 'https://www.kelowna.ca/business-services/business-city/bidding-opportunities', 'municipal', 'British Columbia', 'en', false, true),
('Moncton Bids', 'https://moncton.bidsandtenders.ca/', 'municipal', 'New Brunswick', 'en', false, true),
('Ajax Bids', 'https://ajax.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Thunder Bay Bids', 'https://thunderbay.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Terrebonne SEAO', 'https://www.seao.ca/', 'municipal', 'Quebec', 'fr', true, false),
('St. Johns Bids', 'https://stjohns.bidsandtenders.ca/', 'municipal', 'Newfoundland and Labrador', 'en', false, true),
('Milton Bids', 'https://milton.bidsandtenders.ca/', 'municipal', 'Ontario', 'en', false, true),
('Langley Bids', 'https://tol.bidsandtenders.ca/', 'municipal', 'British Columbia', 'en', false, true);
```

Key enrichment decisions for the portal data:
- **MERX-based portals** (Calgary, Ottawa, Winnipeg, Edmonton via Ariba): Set `requires_login = true`, `enabled = false` because MERX requires registration
- **SEAO-based Quebec portals** (Laval, Gatineau, Longueuil, Sherbrooke, Saguenay, Levis, Trois-Rivieres, Terrebonne): Set `requires_login = true`, `enabled = false`, `language = 'fr'` because SEAO requires registration
- **Alberta Purchasing Connection**: Set `requires_login = true`, `enabled = false`
- **bidsandtenders.ca portals**: Set `requires_login = false`, `enabled = true` (free public access)
- **Federal CanadaBuys**: `requires_login = false`, `enabled = true` (public listings)
- **Provincial portals** (BC Bid, SaskTenders, Ontario Tenders, etc.): Most are public, set accordingly

After creating the file, rebuild the database to run both migrations:
```bash
docker compose down -v  # Remove volumes to reset DB
docker compose up -d
sleep 10
docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) FROM portals;"
# Should return 63
docker compose exec db psql -U procurement -d procurement -c "SELECT level, COUNT(*) FROM portals GROUP BY level ORDER BY level;"
# Should show: federal=2, municipal=50, provincial=11
docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) FROM portals WHERE requires_login = true AND enabled = false;"
# All requires_login portals should be disabled
docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) FROM portals WHERE requires_login = true AND enabled = true;"
# Should return 0
```
  </action>
  <verify>
    <automated>
    cd /Users/clawbot/dev && docker compose down -v && docker compose up -d && sleep 15 && docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) as total FROM portals;" && docker compose exec db psql -U procurement -d procurement -c "SELECT level, COUNT(*) FROM portals GROUP BY level ORDER BY level;" && docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) as login_but_enabled FROM portals WHERE requires_login = true AND enabled = true;" && docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) as enabled_count FROM portals WHERE enabled = true;"
    </automated>
    <manual>Total portals = 63. Federal = 2, Provincial = 11, Municipal = 50. Zero portals have requires_login=true AND enabled=true.</manual>
  </verify>
  <done>
    - 63 portals seeded in the portals table
    - Breakdown: 2 federal, 11 provincial, 50 municipal
    - All portals with requires_login=true have enabled=false
    - Each portal has correct name, url, level, province, language
  </done>
</task>

<task type="auto">
  <name>Task 4: Create Terraform configuration for AWS infrastructure in ca-central-1</name>
  <files>
    terraform/main.tf
    terraform/variables.tf
    terraform/outputs.tf
    terraform/user_data.sh
  </files>
  <action>
Create the complete Terraform configuration to provision all AWS infrastructure from scratch in ca-central-1. Per user decision: LOCAL state only (no S3 backend). Terraform creates everything — no pre-existing VPC, subnets, or EC2.

**1. `terraform/variables.tf`**:
```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ca-central-1"
}

variable "project_name" {
  description = "Project name used for resource tagging"
  type        = string
  default     = "procurement-intel"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.large"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "procurement.eliastools.com"
}

variable "root_domain" {
  description = "Root domain for Route53 zone lookup"
  type        = string
  default     = "eliastools.com"
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to SSH (set to your IP/32 for security)"
  type        = string
  default     = "0.0.0.0/0"
}
```

**2. `terraform/user_data.sh`** — EC2 bootstrap script that installs Docker, Docker Compose, and Git:
```bash
#!/bin/bash
set -euxo pipefail

# Update system (Amazon Linux 2023 uses dnf)
dnf update -y

# Install Docker
dnf install docker -y
systemctl start docker
systemctl enable docker

# Install Docker Compose v2
DOCKER_COMPOSE_VERSION="v2.32.4"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Install Git
dnf install -y git

# Add ec2-user to docker group
usermod -aG docker ec2-user

# Create app directory
mkdir -p /opt/procurement-intel
chown ec2-user:ec2-user /opt/procurement-intel

echo "User data setup complete" > /var/log/user-data-complete.log
```

**3. `terraform/main.tf`** — All AWS resources. CRITICAL: must use local state only (no backend block or use local backend explicitly). Must create:
- VPC with DNS support
- Public subnet
- Internet gateway + route table
- Security group (SSH:22, HTTP:80, HTTPS:443 inbound; all outbound)
- Key pair (Terraform generates TLS private key and creates AWS key pair)
- EC2 instance (t3.large, Amazon Linux 2023, gp3 root volume 50GB)
- Route53 A record for procurement.eliastools.com pointing to EC2 public IP
- Elastic IP for stable public IP address

```hcl
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }

  # LOCAL state per user decision — no S3 backend
}

provider "aws" {
  region = var.aws_region
}

# ============================================================
# VPC AND NETWORKING
# ============================================================

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name    = "${var.project_name}-vpc"
    Project = var.project_name
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name    = "${var.project_name}-public-subnet"
    Project = var.project_name
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-igw"
    Project = var.project_name
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name    = "${var.project_name}-public-rt"
    Project = var.project_name
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ============================================================
# SECURITY GROUP
# ============================================================

resource "aws_security_group" "app" {
  name_prefix = "${var.project_name}-sg-"
  description = "Security group for procurement intelligence platform"
  vpc_id      = aws_vpc.main.id

  # SSH
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  # HTTP (for Let's Encrypt challenge and redirect to HTTPS)
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-sg"
    Project = var.project_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ============================================================
# SSH KEY PAIR
# ============================================================

resource "tls_private_key" "ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = tls_private_key.ssh.public_key_openssh
}

resource "local_file" "ssh_private_key" {
  content         = tls_private_key.ssh.private_key_pem
  filename        = "${path.module}/${var.project_name}-key.pem"
  file_permission = "0400"
}

# ============================================================
# EC2 INSTANCE
# ============================================================

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.main.key_name
  vpc_security_group_ids = [aws_security_group.app.id]
  subnet_id              = aws_subnet.public.id
  user_data              = file("${path.module}/user_data.sh")

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 50
    delete_on_termination = true
    encrypted             = true
  }

  tags = {
    Name    = "${var.project_name}-server"
    Project = var.project_name
  }
}

# ============================================================
# ELASTIC IP
# ============================================================

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = {
    Name    = "${var.project_name}-eip"
    Project = var.project_name
  }
}

# ============================================================
# ROUTE 53 DNS
# ============================================================

data "aws_route53_zone" "main" {
  name         = var.root_domain
  private_zone = false
}

resource "aws_route53_record" "app" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.app.public_ip]
}
```

**4. `terraform/outputs.tf`**:
```hcl
output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Elastic IP address"
  value       = aws_eip.app.public_ip
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i terraform/${var.project_name}-key.pem ec2-user@${aws_eip.app.public_ip}"
}

output "domain" {
  description = "Application domain"
  value       = var.domain_name
}

output "ssh_key_path" {
  description = "Path to SSH private key"
  value       = local_file.ssh_private_key.filename
  sensitive   = true
}
```

After creating all files, validate the Terraform configuration:
```bash
cd terraform
terraform init
terraform validate
terraform plan
```

The plan should show approximately 10-12 resources to create (VPC, subnet, IGW, route table, route table association, security group, key pair, EC2 instance, EIP, Route53 record, local file for SSH key).

Do NOT run `terraform apply` yet — that happens as part of Task 4.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev/terraform && terraform init -input=false && terraform validate && terraform plan -input=false 2>&1; echo "Terraform plan exit code: ${PIPESTATUS[0]:-$?}"</automated>
    <manual>terraform validate succeeds. terraform plan shows ~10-12 resources to create including VPC, EC2, EIP, Route53 record. No errors.</manual>
  </verify>
  <done>
    - terraform init succeeds
    - terraform validate passes with no errors
    - terraform plan shows all expected resources (VPC, subnet, IGW, SG, key pair, EC2 t3.large, EIP, Route53 A record)
    - No S3 backend configured (local state per user decision)
    - Instance type is t3.large
    - Region is ca-central-1
    - Security group allows SSH:22, HTTP:80, HTTPS:443
    - gp3 root volume is 50GB
    - terraform.tfstate is in .gitignore
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 5: Deploy to EC2, configure TLS, and verify end-to-end</name>
  <what-built>
This task requires running `terraform apply` (which costs money and creates AWS resources) and then deploying the application to EC2 with TLS. The executor should:

1. **Run terraform apply:**
```bash
cd /Users/clawbot/dev/terraform
terraform apply -auto-approve
```
Wait for it to complete. Note the public IP and SSH command from outputs.

2. **Wait for EC2 user_data to complete** (Docker install takes 2-3 minutes):
```bash
SSH_KEY="terraform/procurement-intel-key.pem"
PUBLIC_IP=$(cd /Users/clawbot/dev/terraform && terraform output -raw public_ip)
# Wait for instance to be ready
sleep 120
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "cat /var/log/user-data-complete.log"
```

3. **Copy project files to EC2:**
```bash
PUBLIC_IP=$(cd /Users/clawbot/dev/terraform && terraform output -raw public_ip)
SSH_KEY="/Users/clawbot/dev/terraform/procurement-intel-key.pem"

# Copy project files (excluding terraform state, .git, node_modules)
rsync -avz --exclude '.git' --exclude 'terraform/.terraform' --exclude 'terraform/terraform.tfstate*' --exclude 'terraform/*.pem' --exclude 'node_modules' --exclude '.env' -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" /Users/clawbot/dev/ ec2-user@$PUBLIC_IP:/opt/procurement-intel/
```

4. **Create .env on EC2 with strong passwords:**
```bash
ssh -i "$SSH_KEY" ec2-user@$PUBLIC_IP << 'REMOTE_EOF'
cd /opt/procurement-intel
# Generate strong password
DB_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
cat > .env << EOF
POSTGRES_DB=procurement
POSTGRES_USER=procurement
POSTGRES_PASSWORD=${DB_PASS}
DATABASE_URL=postgresql://procurement:${DB_PASS}@db:5432/procurement
OPENAI_API_KEY=sk-placeholder
NEXTAUTH_SECRET=$(openssl rand -base64 32)
EOF
echo "Environment file created"
REMOTE_EOF
```

5. **Start Docker Compose on EC2:**
```bash
ssh -i "$SSH_KEY" ec2-user@$PUBLIC_IP << 'REMOTE_EOF'
cd /opt/procurement-intel
docker compose up --build -d
sleep 30
docker compose ps
docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) FROM portals;"
REMOTE_EOF
```

6. **Obtain TLS certificate with certbot** (DNS must be propagated first):
```bash
ssh -i "$SSH_KEY" ec2-user@$PUBLIC_IP << 'REMOTE_EOF'
# Run certbot as a one-off container
docker run --rm \
  -v procurement-intel_certbot_etc:/etc/letsencrypt \
  -v procurement-intel_certbot_var:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@eliastools.com \
  --agree-tos \
  --no-eff-email \
  -d procurement.eliastools.com
REMOTE_EOF
```

Note: The certbot volume names use the Docker Compose project name prefix. If Docker Compose uses a different prefix (based on directory name), adjust accordingly. Check with `docker volume ls`.

7. **Update nginx.conf to include TLS** — Replace the nginx config with the full TLS version:

The updated `nginx/nginx.conf` should be:
```nginx
# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name procurement.eliastools.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl;
    server_name procurement.eliastools.com;

    ssl_certificate /etc/letsencrypt/live/procurement.eliastools.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/procurement.eliastools.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://web:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Update the file on EC2 and reload nginx:
```bash
# Write the updated nginx.conf locally first, then rsync, then reload
ssh -i "$SSH_KEY" ec2-user@$PUBLIC_IP << 'REMOTE_EOF'
cd /opt/procurement-intel
cat > nginx/nginx.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name procurement.eliastools.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name procurement.eliastools.com;

    ssl_certificate /etc/letsencrypt/live/procurement.eliastools.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/procurement.eliastools.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://web:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_EOF
docker compose restart nginx
REMOTE_EOF
```

8. **Set up certbot auto-renewal** (Let's Encrypt certs expire after 90 days):
```bash
ssh -i "$SSH_KEY" ec2-user@$PUBLIC_IP << 'REMOTE_EOF'
# Create a cron job to renew certificates twice daily (certbot only renews if within 30 days of expiry)
echo '0 0,12 * * * root docker run --rm -v procurement-intel_certbot_etc:/etc/letsencrypt -v procurement-intel_certbot_var:/var/www/certbot certbot/certbot renew --quiet && cd /opt/procurement-intel && docker compose exec -T nginx nginx -s reload' | sudo tee /etc/cron.d/certbot-renew
sudo chmod 644 /etc/cron.d/certbot-renew
echo "Certbot renewal cron installed"
REMOTE_EOF
```

9. **Verify terraform plan shows no drift:**
```bash
cd /Users/clawbot/dev/terraform
terraform plan -detailed-exitcode
# Exit code 0 = no changes (success)
# Exit code 2 = changes detected (drift)
```

10. **Verify end-to-end:**
```bash
# HTTPS should work
curl -s -o /dev/null -w "%{http_code}" https://procurement.eliastools.com/
# Should return 200

# HTTP should redirect to HTTPS
curl -s -o /dev/null -w "%{http_code}" http://procurement.eliastools.com/
# Should return 301

# Follow redirect
curl -sL http://procurement.eliastools.com/ | head -5
# Should show JSON from web stub

# Check TLS certificate
echo | openssl s_client -servername procurement.eliastools.com -connect procurement.eliastools.com:443 2>/dev/null | openssl x509 -noout -subject -issuer -dates
# Should show Let's Encrypt issuer and valid dates
```
  </what-built>
  <how-to-verify>
1. Run `terraform apply` and confirm EC2 instance is created in ca-central-1 with the expected configuration
2. SSH into the EC2 instance and confirm Docker is installed: `docker --version` and `docker compose version`
3. Confirm `docker compose ps` on EC2 shows all 4 services running (db, scraper, web, nginx)
4. Confirm `docker compose exec db psql -U procurement -d procurement -c "SELECT COUNT(*) FROM portals;"` returns 63
5. Visit https://procurement.eliastools.com/ in a browser and confirm:
   - Valid TLS certificate (green padlock, issued by Let's Encrypt)
   - Returns JSON response from the web stub
6. Visit http://procurement.eliastools.com/ and confirm it redirects to HTTPS
7. Run `terraform plan` locally and confirm no drift (exit code 0)
8. Confirm `terraform.tfstate` exists locally (NOT in S3)
  </how-to-verify>
  <resume-signal>Type "approved" if all checks pass, or describe any issues encountered</resume-signal>
</task>

</tasks>

<verification>
After all tasks complete, verify the 4 success criteria from ROADMAP.md:

1. **docker compose up** on EC2 starts all services without errors:
   - `ssh -i terraform/procurement-intel-key.pem ec2-user@$(cd terraform && terraform output -raw public_ip) "cd /opt/procurement-intel && docker compose ps"`
   - All 4 services (db, scraper, web, nginx) should show "Up" or "running"

2. **PostgreSQL schema** contains all tables with correct structure:
   - `ssh ... "cd /opt/procurement-intel && docker compose exec db psql -U procurement -d procurement -c '\dt'"`
   - Tables: listings, portals, scrape_runs
   - `... -c '\di'` shows HNSW index, GIN tsvector index, and all performance indexes
   - `... -c "SELECT COUNT(*) FROM portals;"` returns 63

3. **Terraform plan shows no drift**:
   - `cd terraform && terraform plan -detailed-exitcode` exits with code 0

4. **HTTPS resolves** at procurement.eliastools.com:
   - `curl -s -o /dev/null -w "%{http_code}" https://procurement.eliastools.com/` returns 200
   - `curl -s -o /dev/null -w "%{http_code}" http://procurement.eliastools.com/` returns 301
</verification>

<success_criteria>
- All 4 Docker Compose services running on EC2 without errors
- PostgreSQL schema has listings (with vector(1536), TIMESTAMPTZ columns, composite unique, HNSW index, GIN index), portals (63 rows seeded), and scrape_runs tables
- terraform plan shows no drift after apply
- HTTPS works at procurement.eliastools.com with valid Let's Encrypt certificate
- HTTP redirects to HTTPS
- terraform.tfstate is local (not in S3), and in .gitignore
- No hardcoded secrets in docker-compose.yml or committed files
- PostgreSQL not exposed on public port (Docker network only)
</success_criteria>

<output>
After completion, create `.planning/phases/1/1-01-SUMMARY.md` documenting:
- What was built (infrastructure, schema, services)
- EC2 instance details (IP, instance ID, region)
- Portal count and breakdown
- Schema details (tables, key indexes, constraints)
- Any deviations from the plan
</output>
