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
    province        VARCHAR(50),
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
    source_portal       UUID NOT NULL REFERENCES portals(id),
    source_listing_id   VARCHAR(500) NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    status              VARCHAR(20) NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'closed', 'cancelled', 'awarded')),
    language            VARCHAR(10),
    posting_date        TIMESTAMPTZ,
    closing_date        TIMESTAMPTZ,
    amended_date        TIMESTAMPTZ,
    province            VARCHAR(50),
    raw_location        TEXT,
    classification_codes JSONB DEFAULT '[]'::jsonb,
    value_min           NUMERIC,
    value_max           NUMERIC,
    contact_info        JSONB,
    documents           JSONB DEFAULT '[]'::jsonb,
    revision            INTEGER NOT NULL DEFAULT 1,
    source_url          TEXT,
    embedding           vector(1536),
    embedding_model     VARCHAR(100),
    last_scraped_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_portal, source_listing_id)
);

-- Full-text search index (tsvector GIN index)
CREATE INDEX listings_fts_idx ON listings
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));

-- Vector similarity index (HNSW)
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
