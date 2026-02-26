-- 007_update_nova_scotia_url.sql
-- Update Nova Scotia Procurement portal to new URL

UPDATE portals SET url = 'https://procurement-portal.novascotia.ca/tenders', updated_at = NOW()
WHERE name = 'Nova Scotia Procurement';
