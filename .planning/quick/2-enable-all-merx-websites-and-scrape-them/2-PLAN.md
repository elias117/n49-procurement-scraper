---
phase: quick
plan: 2
type: execute
wave: 1
depends_on: []
files_modified:
  - db/migrations/006_enable_merx_portals.sql
autonomous: false
requirements: [QT-002]

must_haves:
  truths:
    - "All 5 MERX portals have enabled=true in the database"
    - "Scraper can run against each MERX portal without crashing the pipeline"
    - "Any publicly accessible MERX listings are scraped and stored"
  artifacts:
    - path: "db/migrations/006_enable_merx_portals.sql"
      provides: "SQL migration to enable MERX portals"
      contains: "UPDATE portals SET enabled = true"
  key_links:
    - from: "db/migrations/006_enable_merx_portals.sql"
      to: "portals table"
      via: "UPDATE statement"
      pattern: "SET enabled = true.*merx"

user_setup:
  - service: MERX
    why: "MERX portals require login (requires_login=true in seed data). If the user has MERX credentials, they should be available for the browser-use agent."
    dashboard_config:
      - task: "Verify you have MERX account credentials if login is needed"
        location: "https://www.merx.com/ - registration/login page"
---

<objective>
Enable all 5 MERX procurement portals (currently disabled in the database) and run the scraper against them to collect any available listings.

Purpose: MERX portals cover federal, Manitoba provincial, Calgary, Ottawa, and Winnipeg municipal procurement. Enabling them expands coverage from the current set of enabled portals.

Output: Migration file enabling MERX portals, scraper run results showing what each portal yields.
</objective>

<execution_context>
@/Users/clawbot/.claude/get-shit-done/workflows/execute-plan.md
@/Users/clawbot/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@db/migrations/002_seed_portals.sql
@scraper/pipeline/orchestrator.py
@scraper/pipeline/browser_scraper.py
@scraper/db.py
@scraper/main.py

<interfaces>
From scraper/pipeline/orchestrator.py:
```python
def classify_portal(portal: PortalRecord) -> str:
    # Returns "canadabuys", "bidsandtenders", or "browser"
    # MERX portals have merx.com URLs -> classified as "browser"

async def run_pipeline(portal_name=None, skip_embeddings=False, purge=False) -> dict:
    # Can target single portal with --portal flag
```

From scraper/db.py:
```python
def get_enabled_portals(conn) -> list[PortalRecord]:
    # SELECT ... FROM portals WHERE enabled = true ORDER BY name
```

From scraper/models.py:
```python
class PortalRecord(BaseModel):
    id: str; name: str; url: str; level: str
    province: Optional[str]; language: str
    requires_login: bool; enabled: bool
```

The 5 MERX portals currently disabled (enabled=false, requires_login=true):
1. MERX (federal) - https://www.merx.com/
2. MERX Manitoba (provincial) - https://www.merx.com/mbgov
3. Calgary MERX (municipal) - https://www.calgary.merx.com/
4. Ottawa MERX (municipal) - https://www.merx.com/cityofottawa
5. Winnipeg MERX (municipal) - https://www.merx.com/mbgov/cityofwinnipeg

All 5 will be classified as "browser" by classify_portal() since their URLs don't contain "bidsandtenders" and they aren't "CanadaBuys". The browser_scraper.py will handle them via browser-use Agent with keyword search.

NOTE: These portals have requires_login=true. The browser-use agent may encounter login walls. The existing error isolation in process_portal() will catch failures gracefully -- a failed MERX portal will NOT stop other portals from being processed.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create migration to enable MERX portals and run it</name>
  <files>db/migrations/006_enable_merx_portals.sql</files>
  <action>
Create a SQL migration file `db/migrations/006_enable_merx_portals.sql` that enables all 5 MERX portals:

```sql
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
```

Then determine how to run this migration on the production database. Check:
1. Look at how previous migrations were applied (check for a migration runner script, or if they were run manually via `docker compose exec db psql`)
2. Apply the migration to the production database via SSH + docker exec

To verify it took effect, run a query to confirm all 5 portals now show enabled=true:
```sql
SELECT name, enabled FROM portals WHERE name LIKE '%MERX%' OR name LIKE '%merx%' ORDER BY name;
```
  </action>
  <verify>
    Query `SELECT name, enabled FROM portals WHERE name LIKE '%MERX%' ORDER BY name;` returns 5 rows all with enabled=true.
  </verify>
  <done>Migration file exists at db/migrations/006_enable_merx_portals.sql. All 5 MERX portals show enabled=true in the production database.</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 2: Run scraper against MERX portals on EC2</name>
  <what-built>Migration enabling 5 MERX portals has been applied to the production database.</what-built>
  <how-to-verify>
SSH into the EC2 instance and run the scraper targeting each MERX portal individually to see results. The scraper container is already running (`sleep infinity` in prod). Execute inside the scraper container:

```bash
# SSH to EC2 first, then:
docker compose exec scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scraper/main.py --portal "MERX"
docker compose exec scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scraper/main.py --portal "Ottawa MERX"
docker compose exec scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scraper/main.py --portal "Calgary MERX"
docker compose exec scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scraper/main.py --portal "MERX Manitoba"
docker compose exec scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scraper/main.py --portal "Winnipeg MERX"
```

Or run all enabled portals at once (will include both existing + new MERX portals):
```bash
docker compose exec scraper xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scraper/main.py
```

Check the logs for each MERX portal:
- If listings are found: success, note the count
- If login wall blocks scraping: the error isolation will catch it, log will show the error
- If the portal returns 0 listings: may need MERX credentials

After running, check results:
```bash
docker compose exec db psql -U procurement -c "SELECT p.name, COUNT(l.id) as listings FROM portals p LEFT JOIN listings l ON l.source_portal = p.id WHERE p.name LIKE '%MERX%' OR p.name LIKE '%erx%' GROUP BY p.name ORDER BY p.name;"
```
  </how-to-verify>
  <resume-signal>Share the scraper output for each MERX portal. Report which portals succeeded, which hit login walls, and how many listings were found.</resume-signal>
</task>

</tasks>

<verification>
- Migration file exists at db/migrations/006_enable_merx_portals.sql
- All 5 MERX portals show enabled=true in production database
- Scraper has been run against at least one MERX portal
- Results are known (listings found, or login wall identified, or other outcome)
</verification>

<success_criteria>
- 5 MERX portals enabled in production database
- Scraper run attempted against all MERX portals
- Outcome documented (listings scraped, or blockers identified like login requirements)
</success_criteria>

<output>
After completion, create `.planning/quick/2-enable-all-merx-websites-and-scrape-them/2-SUMMARY.md`
</output>
