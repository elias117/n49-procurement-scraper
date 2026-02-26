---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: false
requirements: [QT-009]
must_haves:
  truths:
    - "All 63 portals in the production database have enabled=true"
    - "Migration 008_enable_all_portals.sql has been applied to production DB"
    - "All Docker containers are running the latest code from main"
    - "Scraper container can successfully process all enabled portals"
  artifacts:
    - path: "db/migrations/008_enable_all_portals.sql"
      provides: "Blanket enable migration for all remaining disabled portals"
      contains: "UPDATE portals SET enabled = true WHERE enabled = false"
  key_links:
    - from: "db/migrations/008_enable_all_portals.sql"
      to: "portals table"
      via: "UPDATE WHERE enabled = false"
      pattern: "UPDATE portals SET enabled = true"
---

<objective>
Deploy the latest code to EC2, apply migration 008 to enable all remaining disabled portals (SEAO + 7 SEAO municipals, Alberta Purchasing Connection, Edmonton Procurement), and rebuild/restart containers if needed.

Purpose: All 63 procurement portals should be enabled and scrapeable. Migration 008 already exists in the repo (committed as 6739d93) but has not been applied to the production database.
Output: All portals enabled in production, containers running latest code, verified via portal count query.
</objective>

<execution_context>
@/Users/clawbot/.claude/get-shit-done/workflows/execute-plan.md
@/Users/clawbot/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Key facts:
- EC2: ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248
- EC2 project dir: /opt/procurement-intel
- Docker compose prod: docker compose -f docker-compose.yml -f docker-compose.prod.yml
- Migration 008_enable_all_portals.sql: `UPDATE portals SET enabled = true WHERE enabled = false;`
- Migration 007_update_nova_scotia_url.sql may also not be applied (created in QT-008/quick-3)
- The scraper container runs `sleep infinity` in prod (started via cron or manual exec)
- No scraper/api/web code changes since last deploy (d634eaf) -- only migrations and docs added
- Auto-disable exists: 5 consecutive failures disables a portal (check_auto_disable in db.py)
- 16 portals were originally seeded as disabled (all require_login=true):
  - MERX + 4 MERX municipals (enabled by migration 006)
  - SEAO + 7 SEAO municipals (to be enabled by migration 008)
  - Alberta Purchasing Connection (to be enabled by migration 008)
  - Edmonton Procurement (to be enabled by migration 008)
- Some portals may have been auto-disabled at runtime if they hit 5+ consecutive failures
</context>

<tasks>

<task type="auto">
  <name>Task 1: Deploy latest code and apply migrations to production</name>
  <files></files>
  <action>
1. SSH to EC2 and pull latest code:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && git pull origin main"
```

2. Check if any containers need rebuilding. Since the last deployed code change (d634eaf, browser_scraper.py fix) was already deployed during QT-007, and only migrations/docs have been added since, containers should NOT need rebuilding. Verify by checking the current git HEAD on EC2 matches recent code:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && git log --oneline -5"
```

3. Check current portal state BEFORE applying migrations (to see what needs enabling):
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -c \"SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE enabled) as enabled, COUNT(*) FILTER (WHERE NOT enabled) as disabled FROM portals;\""
```

4. Apply migration 008 (and 007 if not already applied). Since Docker mounts db/migrations to /docker-entrypoint-initdb.d/ (only runs on first DB init), apply manually:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -f /docker-entrypoint-initdb.d/008_enable_all_portals.sql"
```

5. Also re-enable any portals that may have been auto-disabled at runtime (consecutive failure threshold). The migration handles `enabled = false` portals, but run it again to be safe, or alternatively run a direct SQL command:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -c \"UPDATE portals SET enabled = true, updated_at = NOW() WHERE enabled = false;\""
```

6. Verify ALL portals are now enabled:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -c \"SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE enabled) as enabled, COUNT(*) FILTER (WHERE NOT enabled) as disabled FROM portals;\""
```
Expected: total=63, enabled=63, disabled=0.

7. List all portals with their status to confirm:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper python scraper/main.py --list-portals"
```
All 63 portals should show "YES" in the Enabled column.

8. Verify all containers are healthy and running:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml ps"
```
All 5 services (db, scraper, api, web, nginx) should be running.

If any containers are NOT running or unhealthy, restart them:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
```

If scraper or api code had changed (check git log), rebuild those specific containers:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml build scraper api web && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
```
Only do this if containers are stale or code has changed since last build.
  </action>
  <verify>
SSH query returns: total=63, enabled=63, disabled=0. All 5 Docker services show as running.
  </verify>
  <done>All 63 portals enabled in production. Latest code deployed. All containers running.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Verify deployment and portal status</name>
  <what-built>
All 63 portals have been enabled in the production database via migration 008 and a blanket SQL update (to catch any auto-disabled portals). The latest code from main has been deployed to EC2.

To spot-check, verify the web application is accessible and showing portals:
- Visit https://procurement.eliastools.com
- Check that the portal filter dropdown contains all portal names
- Verify existing listings still display correctly

To verify the nightly cron will pick up the new portals, check crontab:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "crontab -l"
```

Optionally, run a quick test scrape of one of the newly-enabled portals (e.g., SEAO):
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper xvfb-run --auto-servernum --server-args=\"-screen 0 1920x1080x24\" python scraper/main.py --portal SEAO"
```
Note: SEAO requires login (requires_login=true), so the browser scraper may hit a login wall. This is expected -- the scraper will report an error and move on. The nightly run handles this gracefully.
  </what-built>
  <how-to-verify>
1. Confirm Task 1 output shows 63/63 portals enabled
2. Visit https://procurement.eliastools.com -- site loads, listings visible
3. Portal filter dropdown should list all 63 portals
4. Docker containers all running (db, scraper, api, web, nginx)
5. (Optional) Test scrape output for one newly-enabled portal
  </how-to-verify>
  <resume-signal>Type "approved" if all portals are enabled and site is working, or describe any issues.</resume-signal>
</task>

</tasks>

<verification>
1. Production DB query: SELECT COUNT(*) FILTER (WHERE enabled) FROM portals = 63
2. --list-portals shows all 63 with "YES"
3. Docker compose ps shows all 5 services running
4. https://procurement.eliastools.com is accessible
</verification>

<success_criteria>
- All 63 portals have enabled=true in production database
- All Docker containers running on EC2 with latest code
- Web application accessible at https://procurement.eliastools.com
- Nightly cron job will pick up all 63 portals on next run
</success_criteria>

<output>
After completion, update .planning/STATE.md with QT-009 entry in Quick Tasks Completed table.
</output>
