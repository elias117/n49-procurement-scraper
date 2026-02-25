-- ============================================================
-- USERS TABLE
-- Simple user accounts for dashboard authentication
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(100) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    password_hash   TEXT NOT NULL,
    last_visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed 3 BD team accounts (passwords: changeme1, changeme2, changeme3)
INSERT INTO users (username, name, password_hash) VALUES
    ('user1', 'BD User 1', '$2b$10$OlWGS5eciDxpCr8yTvW/meQscoXwT9hMgKH/0p1VO34PcF42y8dEm'),
    ('user2', 'BD User 2', '$2b$10$ofSeCnkuv3.ieQ9MpSvE.uJhbh6ZfdF/X2vY3OmeVZL1oKcDZzVbS'),
    ('user3', 'BD User 3', '$2b$10$bcjm9HT2se6gHeHGAW/ifuyWsf8WM.aKH2Jv.vE7ZdFlozs/PZGi.')
ON CONFLICT (username) DO NOTHING;
