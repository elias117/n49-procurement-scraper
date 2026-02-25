# Phase 5 Context: Scheduling and Hardening

## Nightly Scheduling

**Mechanism:** Host-level cron job on EC2 that runs `docker compose exec scraper python main.py` at 2 AM ET. The scraper container stays up (long-lived, idle between runs) so `exec` works without cold-starting. This is simpler than embedding APScheduler inside the container — no scheduler process to manage, no timezone library dependency, and cron is battle-tested for this exact use case.

**Failure behavior:** Continue processing remaining portals if one fails. Per-portal error isolation already exists (try/except in `process_portal` returns error dict). The nightly run should never stop halfway — partial data is better than no data.

**Overlap protection:** Use a flock-style lock file so the cron job is a no-op if a previous run is still going. Simple and reliable.

**Logging:** scrape_runs table in the DB is the primary audit trail (already built). Container stdout logs are sufficient for debugging — Docker's built-in log rotation (configured in hardening) keeps them bounded. No separate log files needed.

## Alerting

**Decision: No alerting.** No CloudWatch alarms, no per-portal yield alerts, no SNS topics. The health page built in Phase 4 provides sufficient visibility into portal status and data freshness. The BD team can check it when needed.

**Roadmap success criteria 2 and 3 are dropped.** Phase 5 success criteria become:
1. Scraper triggers automatically at 2 AM ET nightly
2. Docker Compose hardened for production
3. Listing cleanup policy enforced

## Production Hardening

**Docker Compose prod overlay:** `docker-compose.prod.yml` with pinned image digests, `restart: always` policies, and JSON-file log rotation with max-size/max-file limits. No other dev/prod differences needed — resource limits and environment handling stay as-is.

**Database backups: No.** Data is re-scrapeable. Not worth the complexity for v1.

**Disk cleanup:** Periodic Docker system prune (old images, dangling volumes). Cron job or part of a maintenance script.

**Listing retention:** Delete listings with closing_date older than 1 year. Run as part of the nightly maintenance — after scraping completes, purge stale listings. This keeps the database lean and search results relevant.

## Deferred Ideas

None captured.
