# Phase 3, Plan 01: API Foundation and Schema Migration

## Goal

Stand up the FastAPI service with project structure, DB connection, Pydantic request/response models, Docker Compose integration, nginx routing, schema migration (stored tsvector + original_closing_date), health endpoint, and test infrastructure. After this plan, `docker compose up` starts the API service, `GET /api/health` returns 200, and the test suite runs with mocked fixtures.

## Depends On

Phase 2 complete (listings table populated with ~897 rows, portals seeded).

## Requirements Addressed

SRCH-01 (partial: schema migration for stored tsvector), SRCH-02 (partial: original_closing_date column)

## Files Created/Modified

- `api/` directory (new service)
- `api/Dockerfile`
- `api/requirements.txt`
- `api/main.py`
- `api/config.py`
- `api/db.py`
- `api/routers/__init__.py`
- `api/routers/health.py`
- `api/routers/search.py` (stub)
- `api/search/__init__.py`
- `api/models/__init__.py`
- `api/models/request.py`
- `api/models/response.py`
- `api/tests/__init__.py`
- `api/tests/conftest.py`
- `api/tests/test_health.py`
- `api/tests/test_query_builder.py` (scaffold)
- `api/tests/test_hybrid.py` (scaffold)
- `db/migrations/004_search_layer.sql`
- `docker-compose.yml` (add api service)
- `nginx/nginx.conf` (add /api/ route)
- `pytest.ini` (add api/tests to testpaths)

## Tasks

### Wave 1: Schema Migration + Project Scaffold

#### Task 1.1: Create schema migration for stored tsvector and original_closing_date

**File:** `db/migrations/004_search_layer.sql`
**Action:** Create
**Details:**

```sql
-- 004_search_layer.sql
-- Phase 3: Search layer schema additions

-- Add stored generated tsvector column for index-aligned FTS queries.
-- This guarantees the query expression matches the GIN index exactly,
-- avoiding accidental sequential scans from expression mismatches.
ALTER TABLE listings ADD COLUMN IF NOT EXISTS
    search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED;

-- GIN index on the stored column (coexists with the expression-based
-- listings_fts_idx from 001_initial_schema.sql -- both are valid)
CREATE INDEX IF NOT EXISTS listings_search_vector_idx
    ON listings USING GIN (search_vector);

-- Track original closing date before amendments (per user decision in CONTEXT.md)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS original_closing_date TIMESTAMPTZ;
```

**Fallback:** If `ALTER TABLE ... GENERATED ALWAYS AS` fails with an immutability error (unlikely on PG17 but possible), replace the stored generated column with: (a) a regular `search_vector tsvector` column, (b) a trigger `CREATE TRIGGER ... BEFORE INSERT OR UPDATE ... FOR EACH ROW EXECUTE FUNCTION tsvector_update_trigger(search_vector, 'pg_catalog.english', title, description)`, and (c) an initial `UPDATE listings SET search_vector = to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))`.

**Verify:** Read the file and confirm it contains the three statements. The migration will be applied when Docker Compose rebuilds the DB or is run manually with `psql -f`.

#### Task 1.2: Create API service directory structure, config, and DB helper

**Files:**
- `api/__init__.py`
- `api/config.py`
- `api/db.py`
- `api/search/__init__.py`
- `api/models/__init__.py`
- `api/routers/__init__.py`

**Action:** Create all files
**Details:**

`api/config.py` -- Mirror the pattern from `scraper/config.py`:
```python
"""API service configuration. Loads from environment variables."""
import os
import logging

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required.")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required.")

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

# RRF parameter (k=60 is the original paper default; configurable for tuning)
RRF_K = int(os.environ.get("RRF_K", "60"))

# Oversampling: fetch this many candidates from each sub-query before RRF merge
RRF_OVERSAMPLE_FACTOR = int(os.environ.get("RRF_OVERSAMPLE_FACTOR", "4"))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api")
```

`api/db.py` -- Reuse the exact pattern from `scraper/db.py` (contextmanager, psycopg2, RealDictCursor):
```python
"""Database connection helper for the API service."""
from contextlib import contextmanager
import psycopg2
import psycopg2.extras
from api import config

def get_connection():
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = False
    return conn

@contextmanager
def db_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

All `__init__.py` files should be empty (just `# noqa`).

#### Task 1.3: Create Pydantic request and response models

**Files:**
- `api/models/request.py`
- `api/models/response.py`

**Action:** Create
**Details:**

`api/models/request.py`:
```python
"""Search request model with all filter parameters."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    q: str = Field(default="", description="Search query text")
    mode: str = Field(default="hybrid", pattern="^(hybrid|exact)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=50)
    sort_by: str = Field(
        default="relevance",
        pattern="^(relevance|posting_date|closing_date|value)$",
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    include_closed: bool = Field(default=False)
    regions: Optional[list[str]] = None
    portals: Optional[list[str]] = None
    closing_date_from: Optional[datetime] = None
    closing_date_to: Optional[datetime] = None
    posting_date_from: Optional[datetime] = None
    posting_date_to: Optional[datetime] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    classification_codes: Optional[list[str]] = None
```

`api/models/response.py`:
```python
"""Search response models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class ListingResult(BaseModel):
    id: str
    title: str
    source_portal_name: str
    closing_date: Optional[datetime] = None
    province: Optional[str] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    snippet: str
    posting_date: Optional[datetime] = None

class FacetValue(BaseModel):
    value: str
    count: int

class FacetCounts(BaseModel):
    provinces: list[FacetValue] = []
    portals: list[FacetValue] = []

class SearchResponse(BaseModel):
    results: list[ListingResult] = []
    total_count: int = 0
    page: int = 1
    page_size: int = 25
    total_pages: int = 0
    facets: FacetCounts = FacetCounts()
```

**Verify:** `python -c "from api.models.request import SearchRequest; from api.models.response import SearchResponse; print('Models OK')"` succeeds from project root.

### Wave 2: FastAPI App, Routers, Docker, Nginx

#### Task 2.1: Create FastAPI app with health and search stub routers

**Files:**
- `api/main.py`
- `api/routers/health.py`
- `api/routers/search.py`

**Action:** Create
**Details:**

`api/main.py`:
```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from api.routers import health, search

app = FastAPI(
    title="Procurement Intelligence API",
    description="Hybrid search API for Canadian procurement listings",
    version="0.1.0",
    root_path="/api",  # nginx strips /api/ prefix via proxy_pass
)

app.include_router(health.router)
app.include_router(search.router)
```

`api/routers/health.py`:
```python
"""Health check endpoint."""
from fastapi import APIRouter
from api.db import get_connection

router = APIRouter(tags=["health"])

@router.get("/health")
def health_check():
    """Return API health status and DB connectivity."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM listings")
            count = cur.fetchone()[0]
        conn.close()
        return {"status": "healthy", "listings_count": count}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

`api/routers/search.py` (stub -- will be fully implemented in Plan 3-02):
```python
"""Search endpoint (stub -- implemented in Plan 3-02)."""
from fastapi import APIRouter
from api.models.response import SearchResponse

router = APIRouter(tags=["search"])

@router.get("/search", response_model=SearchResponse)
def search_listings():
    """Search procurement listings. Stub -- returns empty results."""
    return SearchResponse()
```

**Verify:** `python -c "from api.main import app; print(app.title)"` prints "Procurement Intelligence API".

#### Task 2.2: Create Dockerfile and requirements.txt for API service

**Files:**
- `api/Dockerfile`
- `api/requirements.txt`

**Action:** Create
**Details:**

`api/requirements.txt`:
```
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
psycopg2-binary==2.9.10
pydantic>=2.0,<3.0
openai>=1.0,<2.0
tiktoken>=0.5,<1.0
tenacity>=8.0,<9.0
httpx>=0.27,<1.0
bleach>=6.0,<7.0
pytest>=8.0,<9.0
```

`api/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./api/
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/ ./api/

# Run with uvicorn; host 0.0.0.0 so Docker networking works
# Build context is project root (not ./api), so files land at /app/api/
# and package-qualified imports (from api import config) resolve correctly.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Important:** The Dockerfile is at `api/Dockerfile` but the build context must be the project root so `COPY api/ ./api/` works and package imports resolve. See Task 2.3 for the docker-compose.yml build config.

**Verify:** File contents match specification.

#### Task 2.3: Add API service to Docker Compose and nginx

**Files:**
- `docker-compose.yml` (edit)
- `nginx/nginx.conf` (edit)

**Action:** Edit both files
**Details:**

In `docker-compose.yml`, add the `api` service after `scraper` and before `web`:
```yaml
  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "8000"
    networks:
      - internal
```

Note: `context: .` sets the build context to the project root so that `COPY api/ ./api/` in the Dockerfile works and package-qualified imports (`from api import config`) resolve correctly at runtime.

Also add `api` to nginx's `depends_on`:
```yaml
  nginx:
    depends_on:
      - web
      - api
```

In `nginx/nginx.conf`, add inside the **port 443 server block ONLY**, BEFORE the `location /` block:
```nginx
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```

Do NOT add this to the port 80 server block — port 80 should redirect all traffic (including `/api/`) to HTTPS. The existing `return 301 https://$host$request_uri` catch-all handles this correctly.

Note: The trailing `/` on `proxy_pass http://api:8000/` strips the `/api/` prefix so FastAPI sees `/health`, `/search`, etc.

**Verify:** `grep -c "api:" docker-compose.yml` returns at least 1. `grep -c "proxy_pass http://api:8000" nginx/nginx.conf` returns at least 1.

### Wave 3: Test Infrastructure

#### Task 3.1: Create test fixtures and scaffold test files

**Files:**
- `api/tests/__init__.py`
- `api/tests/conftest.py`
- `api/tests/test_health.py`
- `api/tests/test_query_builder.py` (scaffold with placeholder tests)
- `api/tests/test_hybrid.py` (scaffold with placeholder tests)
- `api/tests/test_facets.py` (scaffold with placeholder tests)

**Action:** Create
**Details:**

`api/tests/conftest.py`:
```python
"""Shared test fixtures for the search API."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)

@pytest.fixture
def mock_db_connection():
    """Mock psycopg2 connection with cursor context manager."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_conn._mock_cursor = mock_cursor
    return mock_conn

@pytest.fixture
def sample_portal_id():
    return str(uuid.uuid4())

@pytest.fixture
def sample_listing_row(sample_portal_id):
    """A dict mimicking a RealDictCursor row from the listings table."""
    return {
        "id": str(uuid.uuid4()),
        "title": "IT Infrastructure Modernization Services",
        "description": "Cloud migration and server consolidation for federal departments.",
        "source_portal": sample_portal_id,
        "portal_name": "CanadaBuys",
        "closing_date": datetime.now(timezone.utc) + timedelta(days=30),
        "province": "Ontario",
        "value_min": 500000.0,
        "value_max": 2000000.0,
        "posting_date": datetime.now(timezone.utc) - timedelta(days=5),
        "classification_codes": [
            {"system": "GSIN", "code": "N7030", "description": "IT Equipment"},
        ],
        "snippet": "Cloud migration and <mark>server</mark> consolidation...",
        "rrf_score": 0.032,
    }

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client returning a fixed embedding vector."""
    mock_client = MagicMock()
    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = [0.1] * 1536
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [mock_embedding_data]
    mock_client.embeddings.create.return_value = mock_embedding_response
    return mock_client
```

`api/tests/test_health.py`:
```python
"""Tests for health endpoint."""
from unittest.mock import patch, MagicMock

def test_health_returns_200(client):
    """Health endpoint returns 200 with listing count."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = (897,)
    mock_conn.cursor.return_value = mock_cursor

    with patch("api.routers.health.get_connection", return_value=mock_conn):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["listings_count"] == 897

def test_health_db_error(client):
    """Health endpoint returns unhealthy on DB error."""
    with patch("api.routers.health.get_connection", side_effect=Exception("conn failed")):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
```

`api/tests/test_query_builder.py` (scaffold -- real tests added in Plan 3-02):
```python
"""Unit tests for dynamic SQL filter construction.
Scaffold -- tests added in Plan 3-02 when query_builder.py is implemented."""

def test_placeholder():
    """Remove when real tests are added."""
    assert True
```

`api/tests/test_hybrid.py` (scaffold):
```python
"""Unit tests for RRF hybrid search logic.
Scaffold -- tests added in Plan 3-02 when hybrid.py is implemented."""

def test_placeholder():
    """Remove when real tests are added."""
    assert True
```

`api/tests/test_facets.py` (scaffold):
```python
"""Unit tests for facet count queries.
Scaffold -- tests added in Plan 3-03 when facets.py is implemented."""

def test_placeholder():
    """Remove when real tests are added."""
    assert True
```

**Verify:** `cd /Users/clawbot/dev && python -m pytest api/tests/test_health.py -x -q` passes (2 tests).

#### Task 3.2: Update pytest.ini to include api/tests

**File:** `pytest.ini`
**Action:** Edit
**Details:**

Change `testpaths = scraper/tests` to `testpaths = scraper/tests api/tests`.

**Verify:** `cd /Users/clawbot/dev && python -m pytest api/tests/ -x -q` runs and passes.

## Plan Verification

Run all of these in sequence:
1. `python -m pytest api/tests/ -x -q` -- all tests pass (2 health tests + 3 placeholders)
2. `python -c "from api.main import app; print(app.title)"` -- prints "Procurement Intelligence API"
3. `python -c "from api.models.request import SearchRequest; sr = SearchRequest(q='test'); print(sr.mode)"` -- prints "hybrid"
4. `grep 'api:' docker-compose.yml` -- shows the api service definition
5. `grep 'proxy_pass http://api:8000' nginx/nginx.conf` -- shows the nginx proxy route
6. `cat db/migrations/004_search_layer.sql` -- shows search_vector and original_closing_date additions
