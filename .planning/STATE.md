# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.
**Current focus:** Phase 2 - Scraper Pipeline (EXECUTING)

## Current Position

Phase: 2 of 5 (Scraper Pipeline) — EXECUTING
Plan: 2-02 of 4 in current phase (Wave 1)
Status: Plan 2-01 complete — ready for Plan 2-02
Last activity: 2026-02-24 — Plan 2-01 foundation layer complete

Progress: [===.......] 27% (3/11 tasks across 4 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: ~10 min
- Total execution time: ~20 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 1/1 | ~15min | ~15min |
| 2 | 1/4 | ~5min | ~5min |

**Recent Trend:**
- Last 5 plans: 1-01 (complete), 2-01 (complete)
- Trend: accelerating

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: Browser Use + instructor chosen for generalist scraping across 63 diverse portal layouts (instructor recommended over LangExtract per Phase 2 research)
- [Pre-phase]: pgvector chosen over Elasticsearch — single data store for structured + vector data
- [Pre-phase]: Single EC2 + Docker Compose — simple and cheap for internal tool
- [Pre-phase]: APScheduler over Celery — no broker needed for a single nightly batch
- [Pre-phase]: text-embedding-3-small locked as embedding model — model changes require full re-indexing
- [Phase 1]: Stub services for Phase 1 — scraper sleeps, web returns JSON health endpoint
- [Phase 1]: Terraform lock file committed for reproducible provider versions
- [Phase 1]: Port 443 verified as production-only concern (EC2 target)
- [Phase 1]: rsync installed on EC2 (not in AL2023 by default)
- [Phase 1]: cronie installed on EC2 for certbot renewal cron
- [Phase 2]: Pydantic v2 BaseModel for all data models (matches DB schema exactly)
- [Phase 2]: psycopg2 direct connections, no pool needed for sequential batch processing
- [Phase 2]: xmax=0 trick in RETURNING clause to distinguish new vs updated upsert rows
- [Phase 2]: Embedding vectors passed as string format '[0.1, 0.2, ...]' for pgvector compatibility

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2]: ~~Investigate CanadaBuys API~~ RESOLVED: CanadaBuys has structured CSV open data files — zero-cost ingestion path via direct download
- [Phase 2]: Benchmark LLM API cost on 5 representative portals before enabling all 63 — addressed by Plan 2-04 Task 3 (live benchmark checkpoint)
- [Phase 2]: Audit robots.txt compliance — deferred to execution, robots.txt check recommended but not blocking

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 2-01-PLAN.md
Resume file: .planning/phases/2/2-02-PLAN.md
