-- 006_enable_merx_portals.sql
-- Enable all MERX procurement portals for scraping

UPDATE portals SET enabled = true, updated_at = NOW()
WHERE name IN (
    'MERX',
    'MERX Manitoba',
    'Calgary MERX',
    'Ottawa MERX',
    'Winnipeg MERX'
);
