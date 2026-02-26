-- Enable all remaining disabled portals (SEAO, Alberta Purchasing Connection, Edmonton)
UPDATE portals SET enabled = true WHERE enabled = false;
