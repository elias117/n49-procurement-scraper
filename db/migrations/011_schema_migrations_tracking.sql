-- Schema migrations tracking table.
-- Records which migration files have been applied to prevent re-runs.
-- The migration runner creates this table on first run if it doesn't exist,
-- but this file is included for completeness and manual bootstrap.

CREATE TABLE IF NOT EXISTS schema_migrations (
    id              SERIAL PRIMARY KEY,
    filename        VARCHAR(500) NOT NULL UNIQUE,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum        VARCHAR(64)  -- SHA-256 of the migration file at apply time
);
