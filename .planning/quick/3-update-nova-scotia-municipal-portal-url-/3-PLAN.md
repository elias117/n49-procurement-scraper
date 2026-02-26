---
phase: quick-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - db/migrations/007_update_nova_scotia_url.sql
autonomous: false
requirements: [QT-008]
must_haves:
  truths:
    - "Nova Scotia Procurement portal URL is updated to https://procurement-portal.novascotia.ca/tenders in the database"
    - "Scraper runs successfully against the new URL and finds listings (or cleanly reports zero)"
  artifacts:
    - path: "db/migrations/007_update_nova_scotia_url.sql"
      provides: "URL update migration"
      contains: "UPDATE portals SET url"
  key_links:
    - from: "db/migrations/007_update_nova_scotia_url.sql"
      to: "portals table"
      via: "UPDATE WHERE name = 'Nova Scotia Procurement'"
      pattern: "UPDATE portals SET url"
---

<objective>
Update the Nova Scotia Procurement portal URL from `https://procurement.novascotia.ca/` to `https://procurement-portal.novascotia.ca/tenders` and run a scrape job against it on EC2.

Purpose: The old Nova Scotia procurement URL may be outdated/broken. The new URL points to their current procurement portal.
Output: Migration file committed, URL updated in production DB, scrape job executed.
</objective>

<execution_context>
@/Users/clawbot/.claude/get-shit-done/workflows/execute-plan.md
@/Users/clawbot/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Key facts:
- Portal name in DB: "Nova Scotia Procurement" (provincial level, NOT municipal despite task title)
- Current URL: https://procurement.novascotia.ca/
- New URL: https://procurement-portal.novascotia.ca/tenders
- Portal is already enabled=true
- Scraper classifies it as "browser" type (uses browser-use agent) since it's not CanadaBuys and not bidsandtenders
- EC2: ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248
- EC2 project dir: /opt/procurement-intel
- Migration pattern: SQL files in db/migrations/, applied via docker compose exec -T db psql
- Previous migration: 006_enable_merx_portals.sql
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create URL update migration and deploy to EC2</name>
  <files>db/migrations/007_update_nova_scotia_url.sql</files>
  <action>
1. Create migration file `db/migrations/007_update_nova_scotia_url.sql`:

```sql
-- 007_update_nova_scotia_url.sql
-- Update Nova Scotia Procurement portal to new URL

UPDATE portals SET url = 'https://procurement-portal.novascotia.ca/tenders', updated_at = NOW()
WHERE name = 'Nova Scotia Procurement';
```

2. Commit the migration file locally.

3. Deploy to EC2:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && git pull origin main"
```

4. Apply the migration on EC2:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && docker compose exec -T db psql -U procurement -d procurement -f /docker-entrypoint-initdb.d/007_update_nova_scotia_url.sql"
```

5. Verify the URL was updated:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && docker compose exec -T db psql -U procurement -d procurement -c \"SELECT name, url FROM portals WHERE name = 'Nova Scotia Procurement';\""
```

The query should show url = `https://procurement-portal.novascotia.ca/tenders`.
  </action>
  <verify>
SSH query shows Nova Scotia Procurement portal URL is `https://procurement-portal.novascotia.ca/tenders`
  </verify>
  <done>Migration file committed, pushed, deployed to EC2, and verified in production DB</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Run scraper against Nova Scotia Procurement and verify results</name>
  <what-built>
Run the scraper on EC2 against the updated Nova Scotia Procurement portal:

```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && docker compose exec -T scraper xvfb-run --auto-servernum --server-args=\"-screen 0 1920x1080x24\" python scraper/main.py --portal \"Nova Scotia Procurement\""
```

This uses the browser-use agent to navigate the new URL and extract procurement listings. After the scrape completes, check what was found:

```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && docker compose exec -T db psql -U procurement -d procurement -c \"SELECT COUNT(*) as total, MAX(created_at) as latest FROM listings WHERE source_portal = (SELECT id FROM portals WHERE name = 'Nova Scotia Procurement');\""
```
  </what-built>
  <how-to-verify>
1. Review the scraper output -- did it successfully navigate the new URL?
2. Check listing count -- were any procurement listings found and saved?
3. If the scraper errored (e.g., page structure unexpected for browser-use), report the error so we can adjust.
  </how-to-verify>
  <resume-signal>Share the scraper output and listing count. Report success or any errors encountered.</resume-signal>
</task>

</tasks>

<verification>
1. Migration file exists at db/migrations/007_update_nova_scotia_url.sql
2. Production DB shows updated URL for Nova Scotia Procurement
3. Scraper has been run against the portal (results verified by human)
</verification>

<success_criteria>
- Nova Scotia Procurement portal URL updated to https://procurement-portal.novascotia.ca/tenders in production
- Scraper executed against the new URL (success or actionable error reported)
</success_criteria>

<output>
After completion, update .planning/STATE.md with QT-008 entry in Quick Tasks Completed table.
</output>
