---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: false
requirements: [QT-010]

must_haves:
  truths:
    - "Latest scraper code (7 commits since last sync) is deployed to EC2"
    - "Full scraper pipeline runs against all 63 enabled portals"
    - "New/updated listings are visible in the production database"
  artifacts:
    - path: "remote:/opt/procurement-intel/scraper/"
      provides: "Updated scraper code with detail-page enrichment and source_url fixes"
    - path: "remote:/opt/procurement-intel/logs/manual-scrape.log"
      provides: "Scrape run output log"
  key_links:
    - from: "local scraper/ directory"
      to: "remote /opt/procurement-intel/scraper/"
      via: "SCP file sync"
      pattern: "scp -r"
    - from: "docker compose exec scraper"
      to: "python scraper/main.py"
      via: "container execution"
      pattern: "docker compose.*exec.*scraper"
---

<objective>
Deploy the latest scraper code to EC2 and run a full scraper job across all 63 portals. Since QT-009 (2026-02-26), there have been 7 scraper commits adding detail-page enrichment for sparse listings, browser-use API compatibility fixes, and source_url corrections. These need to be deployed before running the scraper to ensure the highest quality data extraction.

Purpose: Populate the production database with current procurement listings from all 63 portals using the latest scraper improvements.
Output: Updated production database with fresh listings, scrape run log.
</objective>

<execution_context>
@/Users/clawbot/.claude/get-shit-done/workflows/execute-plan.md
@/Users/clawbot/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/PROJECT.md
@.planning/quick/4-enable-all-disabled-portals-and-deploy-t/4-SUMMARY.md

Key facts:
- EC2 is NOT a git repo. Use SCP to sync files (established pattern from QT-009).
- SSH: `ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248`
- Project dir on EC2: `/opt/procurement-intel`
- Docker Compose prod overlay: `docker compose -f docker-compose.yml -f docker-compose.prod.yml`
- Scraper container runs with `sleep infinity` in prod (cron triggers via `docker compose exec`)
- xvfb-run is needed for Chromium (headless=False to avoid 403 blocks)
- Scraper processes portals sequentially (4GB memory constraint)
- 63 portals enabled, 3 types: canadabuys (1), bidsandtenders (~29), browser (~33)

Files changed since last EC2 sync (commit d9be975):
- scraper/config.py (BROWSER_DETAIL_MAX_PAGES setting)
- scraper/pipeline/bidsandtenders.py (detail page enrichment, source_url fix)
- scraper/pipeline/browser_scraper.py (detail page enrichment, browser-use API fixes)
- scraper/pipeline/extraction.py (sparse detection, detail page extraction)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Sync latest scraper code to EC2 and rebuild container</name>
  <files>remote: /opt/procurement-intel/scraper/</files>
  <action>
Sync the updated scraper files to EC2 and rebuild the scraper Docker image to pick up the changes.

**Step 1: SCP the entire scraper directory to EC2** (EC2 is not a git repo -- SCP is the established deployment pattern):
```bash
scp -i terraform/procurement-intel-key.pem -r scraper/ ec2-user@16.54.103.248:/opt/procurement-intel/scraper/
```

Also sync config.py specifically (it's inside the scraper dir but confirm):
```bash
scp -i terraform/procurement-intel-key.pem scraper/config.py ec2-user@16.54.103.248:/opt/procurement-intel/scraper/config.py
```

**Step 2: SSH into EC2 and rebuild the scraper container** to pick up the new code:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml build scraper && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d scraper"
```

**Step 3: Verify the new code is deployed** by checking one of the changed files inside the running container:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec scraper grep -c '_is_sparse' scraper/pipeline/extraction.py"
```
This should return a nonzero count (the `_is_sparse` function was added in the detail-page enrichment commits).

Also verify all 5 containers are running:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps"
```
  </action>
  <verify>
    <automated>ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper grep -c '_is_sparse' scraper/pipeline/extraction.py && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format 'table {{.Name}}\t{{.Status}}' | grep -c 'Up'"</automated>
  </verify>
  <done>Latest scraper code deployed to EC2, scraper container rebuilt with detail-page enrichment and source_url fixes, all 5 containers running.</done>
</task>

<task type="auto">
  <name>Task 2: Run full scraper pipeline on all 63 portals</name>
  <files>remote: /opt/procurement-intel/logs/</files>
  <action>
Run the full scraper pipeline against all 63 enabled portals. This will take a significant amount of time (portals are processed sequentially due to memory constraints). The scraper handles per-portal error isolation, so individual portal failures won't stop the pipeline.

**Step 1: Record baseline listing count** before the scrape:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -t -c 'SELECT COUNT(*) FROM listings;'"
```

**Step 2: Start the scraper run via SSH.** Run it with `--purge` flag to clean up any non-matching listings after scraping. Use nohup so the process continues if SSH disconnects:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper bash -c 'nohup xvfb-run --auto-servernum --server-args=\"-screen 0 1920x1080x24\" python scraper/main.py --purge > /tmp/manual-scrape.log 2>&1 &' && echo 'Scraper started in background'"
```

**Step 3: Monitor progress periodically** by tailing the log:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper tail -50 /tmp/manual-scrape.log 2>/dev/null || echo 'Log not ready yet'"
```

Check if the scraper process is still running:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper pgrep -f 'python scraper/main.py' && echo 'Still running' || echo 'Completed'"
```

**Step 4: Once complete**, check the log for the PIPELINE COMPLETE summary line showing total portals processed, listings found/new/updated, and errors:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper tail -20 /tmp/manual-scrape.log"
```

**Step 5: Check database listing count** to confirm data was written:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -c 'SELECT COUNT(*) as total_listings FROM listings;'"
```

Also get per-portal breakdown:
```bash
ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 \
  "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -c \"SELECT p.name, COUNT(l.id) as listings FROM portals p LEFT JOIN listings l ON p.id = l.portal_id WHERE p.enabled = true GROUP BY p.name ORDER BY listings DESC LIMIT 30;\""
```

**Important:** This is a long-running operation (potentially 1-2 hours for 63 portals). Use `run_in_background` for the initial SSH command and poll periodically. Do NOT wait synchronously.
  </action>
  <verify>
    <automated>ssh -i terraform/procurement-intel-key.pem ec2-user@16.54.103.248 "cd /opt/procurement-intel && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T scraper grep 'PIPELINE COMPLETE' /tmp/manual-scrape.log && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U procurement -d procurement -t -c 'SELECT COUNT(*) FROM listings;'"</automated>
  </verify>
  <done>Full pipeline run completed across all 63 portals. PIPELINE COMPLETE log line present with summary stats. Listing count in database has increased from pre-run baseline.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Verify listings on production dashboard</name>
  <files>n/a</files>
  <action>
Human verifies the scrape results are visible and correct on the production dashboard.

What was built: Deployed latest scraper code to EC2 and ran a full scraper job across all 63 portals. The database should now contain fresh procurement listings with improved data quality (detail-page enrichment for sparse listings, corrected source URLs).

How to verify:
1. Visit https://procurement.eliastools.com and log in
2. Check the dashboard shows listings from multiple portals (not just CanadaBuys)
3. Click into a few listings from different portals -- verify they have:
   - A title and description (not sparse/empty)
   - A working source URL that links to the actual portal page (not an external redirect)
4. Check the Scraper Health / audit page to see which portals succeeded vs failed
5. Confirm the overall listing count looks reasonable (should be significantly more than the ~7 keyword-matched listings from the previous run)

Resume signal: Type "approved" if listings look good, or describe any issues you see (missing portals, broken links, empty descriptions, etc.)
  </action>
  <verify>Human approval of dashboard listing quality</verify>
  <done>User confirms listings from multiple portals are visible with complete data (titles, descriptions, valid source URLs).</done>
</task>

</tasks>

<verification>
- Latest scraper code (7 commits) synced to EC2 via SCP
- Scraper container rebuilt with new code
- Full pipeline ran against all 63 enabled portals
- PIPELINE COMPLETE log entry with stats
- Production database contains fresh listings
- Dashboard shows listings from multiple portals with complete data
</verification>

<success_criteria>
1. All 5 Docker containers running on EC2 after rebuild
2. Scraper pipeline completed (PIPELINE COMPLETE in log)
3. Database listing count increased from pre-run value
4. Listings visible on procurement.eliastools.com dashboard with improved data quality
</success_criteria>

<output>
After completion, create `.planning/quick/5-run-a-full-scraper-job-on-ec2-and-update/5-SUMMARY.md`
</output>
