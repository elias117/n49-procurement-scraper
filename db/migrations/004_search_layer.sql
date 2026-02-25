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
