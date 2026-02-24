# Domain Pitfalls: Procurement Intelligence Platform

**Domain:** Government procurement portal scraping + AI extraction + semantic search
**Researched:** 2026-02-24
**Overall confidence:** MEDIUM-HIGH (core scraping/Playwright verified across multiple sources; Browser Use in production is newer territory with lower confidence)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or the team stops trusting the tool.

---

### Pitfall 1: Silent Extraction Failure Across Portals

**What goes wrong:** A portal changes its layout, adds pagination, or restructures HTML. The scraper continues running and reports "success" but extracts zero or partial listings. The nightly job completes with exit code 0. No alert fires. The database silently stops receiving new listings from that portal — sometimes for weeks.

**Why it happens:** Scraper health is measured by job completion, not data completeness. Without per-portal yield tracking, a zero-result run for a single portal is indistinguishable from "no new listings tonight." With 63 portals, manual spot-checking is impractical.

**Consequences:** BD team misses active tenders on silent portals. Trust in the platform collapses when they discover outdated data. Root cause is hard to trace without historical yield baselines.

**Prevention:**
- Track per-portal listing count per run in a `scrape_runs` audit table
- Alert when a portal yields 0 listings AND it yielded >0 on the prior run
- Alert when a portal's 7-day average drops more than 50%
- Add a health check query to the dashboard showing "last scraped / listings found" per portal

**Warning signs:**
- A portal's listing count in the DB hasn't changed in 3+ days
- The BD team says "I checked [portal] manually and saw listings that aren't here"
- Nightly job duration drops significantly (it's completing faster because it's extracting nothing)

**Phase to address:** Phase 1 (scraper foundation) — build yield tracking before you have 63 portals running

---

### Pitfall 2: LLM Extraction Hallucination on Critical Fields

**What goes wrong:** LangExtract + an LLM infers a closing date, dollar value, or NAICS code that isn't actually on the page — or subtly misreads an ambiguous date format. The extracted record looks valid and passes schema validation but contains fabricated field values. A BD team member chases a $2M contract only to find it closed two weeks ago.

**Why it happens:** LLMs trained to be helpful will guess rather than return null when a field is ambiguous or partially visible. Dates are particularly vulnerable: "Closing: February 14, 2025" on a portal scraped in 2026 might get hallucinated to 2026. Dollar values with unusual formatting ("$1.2M" vs "1,200,000") are frequently misread.

**Consequences:** The BD team discovers wrong dates or values, stops trusting the data, and reverts to manually checking portals — defeating the platform's purpose entirely.

**Prevention:**
- Use LangExtract's source-grounding feature: every extracted field must map back to a character offset in the source text. Treat any field without a grounded span as suspect
- Add a post-extraction validation step: closing_date must be >= posting_date, closing_date must be within 0-730 days of today, dollar values must be parseable numbers within plausible range
- For dates specifically: store the raw extracted string alongside the parsed date so anomalies can be spotted
- Flag records with missing required fields (closing_date, title) for manual review rather than silently dropping them
- Run a weekly spot-check: randomly sample 20 extracted records and compare against the live portal

**Warning signs:**
- Closing dates clustering implausibly (e.g., all showing today's date or the exact same date)
- Dollar values of exactly $0 or round numbers like $1,000,000 appearing frequently
- Source grounding spans pointing to navigation/boilerplate text rather than content fields

**Phase to address:** Phase 1 (extraction schema design) — define validation rules before filling the database

---

### Pitfall 3: Playwright / Chromium Memory Exhaustion on Single EC2

**What goes wrong:** Each Playwright browser instance running against a portal consumes RAM. With concurrent scraping across 63 portals, and if browser contexts aren't closed properly (especially on error paths), zombie Chromium processes accumulate. The EC2 instance runs out of memory partway through the nightly job. Later portals in the queue never run. No alert fires because Docker Compose restarts the scraper container but the nightly cron has already finished.

**Why it happens:** Chromium uses `/dev/shm` (shared memory) heavily. The default Docker container `/dev/shm` is 64MB — far too small. Without `--disable-dev-shm-usage` and explicit `try/finally` cleanup, browser instances accumulate. A single crashed page can leave a ghost browser consuming 200-400MB.

**Consequences:** Portals later in the nightly queue are never scraped. Memory pressure also degrades PostgreSQL query performance on the same instance. Can take days to notice if there's no memory alerting.

**Prevention:**
- Always close browser contexts in `try/finally` blocks — never assume success paths
- Add `--disable-dev-shm-usage` and `--disable-cache` to Chromium launch flags in Docker
- Set `shm_size: '2gb'` in docker-compose.yml for the scraper service
- Implement a scraper concurrency limit: run no more than 3-5 portals in parallel regardless of available RAM
- Set hard memory limits on the scraper container in docker-compose.yml (`mem_limit: 4g`)
- Monitor EC2 memory via CloudWatch; alert at 80% utilization

**Warning signs:**
- EC2 RAM usage climbing and not releasing after the scraper container restarts
- `docker stats` showing scraper container memory growing monotonically during a run
- Nightly run taking progressively longer each week (more portals failing to completion)

**Phase to address:** Phase 1 (scraper infrastructure) — configure Docker from the start; expensive to fix post-deployment

---

### Pitfall 4: LLM API Cost Explosion at Scale

**What goes wrong:** Browser Use uses an LLM at every navigation step to decide what to do next. LangExtract sends page content to an LLM for field extraction. At 63 portals with multiple pages each, and with context windows growing per multi-turn agent session, token costs can reach $50-200+/night depending on portal complexity and model choice. What costs $5 in dev testing costs $150/night in production.

**Why it happens:** AI browser agents accumulate context across steps — by step 10 of navigating a complex portal, you're sending 40,000+ tokens to get a 100-token response. LangExtract sends full page content for extraction. Multiply by 63 portals, multiple pages per portal, nightly frequency.

**Consequences:** Monthly LLM API bill exceeds the value of the tool for an internal team. Forces emergency architectural changes to switch models or add caching.

**Prevention:**
- Benchmark token costs per portal BEFORE building the full pipeline. Run 5 representative portals, measure token consumption, extrapolate to 63
- Use the cheapest capable model for extraction (Gemini Flash, GPT-4o-mini) rather than expensive frontier models. Reserve powerful models for difficult portals only
- Implement content deduplication: hash page content before sending to LLM. If content unchanged since last night, skip extraction entirely
- Use LangExtract's targeted extraction: pass only the relevant page section (main content area), not the full HTML including nav/footer/scripts
- Set per-run token budgets with hard stops; log token usage per portal run to track outliers

**Warning signs:**
- A single portal's scrape taking >10 minutes (agent is in a navigation loop)
- LLM API bills increasing week over week even though portal count is stable
- Browser Use agent making >20 steps to complete a single portal scrape

**Phase to address:** Phase 1 (before scaling to all 63 portals) — establish cost baseline on a representative sample first

---

### Pitfall 5: Embedding Model Lock-In / Inconsistency

**What goes wrong:** Semantic search is built using embedding model version X. Later, the model is upgraded or swapped (e.g., OpenAI releases a better text-embedding-3-large, or the team switches from OpenAI to a local model for cost). The new model produces vectors in a different space — now the 50,000 existing embeddings are incompatible with new query vectors. Semantic search silently returns wrong results. Re-embedding the entire corpus takes hours and requires a migration.

**Why it happens:** Embedding vectors are model-specific. A document embedded with `text-embedding-3-small` and a query embedded with `text-embedding-3-large` will not produce meaningful similarity scores. This is often discovered late because wrong results look plausible (they return something, just not the right things).

**Consequences:** Semantic search degrades without obvious error signals. "Natural language search works" becomes "natural language search sort of works" — the team stops using it.

**Prevention:**
- Store the model name and version with every embedding in the database (`embedding_model VARCHAR` column)
- Document the embedding model selection as an architectural decision; treat model changes as breaking changes requiring full re-indexing
- Choose a stable, widely-supported model at the start (OpenAI `text-embedding-3-small` is a strong default — cost-effective, stable, 1536 dimensions)
- Build a re-embedding migration script in Phase 1; plan to run it if the model ever changes
- Test semantic search quality with 20 representative procurement queries before declaring it "done"

**Warning signs:**
- Semantic search returns listings that are obviously off-topic for clear queries
- Similarity scores for clearly relevant listings dropping below threshold
- Two queries that should return similar results returning completely different result sets

**Phase to address:** Phase 2 (search implementation) — lock model before populating the database at scale

---

## Moderate Pitfalls

---

### Pitfall 6: Date and Timezone Corruption

**What goes wrong:** Canadian procurement portals use various date formats and almost none of them specify timezone explicitly. "Closes March 15, 2026 at 2:00 PM" — is that ET, PT, MT, or CT? The scraper stores all dates as UTC without normalization. Users see closing times that are off by 3 hours. A team member submits a bid thinking they have until 2:00 PM ET but the portal closed at 2:00 PM PT.

**Why it happens:** Government portals are built by different agencies across provinces with inconsistent date display standards. LLMs often just extract the string they see without reasoning about timezone. Python `datetime.strptime` silently produces a naive datetime that gets stored as UTC.

**Prevention:**
- Store all dates as UTC in PostgreSQL with `TIMESTAMPTZ` columns (never `TIMESTAMP`)
- Build a portal-specific timezone registry: record the expected timezone for each of the 63 portals based on their jurisdiction (federal = ET, BC = PT, Alberta = MT, etc.)
- Display dates to users with both the local time and timezone label ("March 15, 2026 2:00 PM ET")
- Flag dates where the raw extracted string is ambiguous for manual review
- Use the `python-dateutil` or `dateparser` library rather than manual strptime parsing

**Warning signs:**
- Extracted closing times clustering at noon or midnight (LLM is stripping time components)
- Duplicate listings with different closing times for the same tender
- Dates appearing in the past for listings that are still open on the portal

**Phase to address:** Phase 1 (data schema) — `TIMESTAMPTZ` columns cannot be added retroactively without data migration

---

### Pitfall 7: Deduplication Failure — Same Listing, Multiple Records

**What goes wrong:** The same tender appears on CanadaBuys AND on a provincial portal AND on MERX. The scraper treats each source independently and creates 3 separate listings. Users see the same opportunity 3 times and don't know which is canonical. Amendment notices also create duplicates if treated as new listings rather than updates to existing records.

**Why it happens:** Without a cross-portal deduplication strategy, each scrape run creates new records. Government tenders often share reference numbers (GSIN, solicitation numbers) that could serve as deduplication keys, but these numbers aren't always extracted reliably.

**Prevention:**
- Design the schema with a `source_portal` + `source_listing_id` composite unique constraint as the primary deduplication key
- Extract solicitation/reference numbers as first-class fields; use them for cross-portal deduplication where possible
- Implement upsert semantics: insert or update on `(source_portal, source_listing_id)` rather than always inserting
- Track amendment history: amendments should update the existing record with a version/amendment counter, not create new records
- Add a `canonical_listing_id` column for explicitly linking duplicates when manual deduplication is needed later

**Warning signs:**
- Listing count growing faster than expected per nightly run
- Users complaining about seeing the same opportunity multiple times in search results
- Dollar value or closing date differing between what look like the same opportunity

**Phase to address:** Phase 1 (schema design) — upsert semantics must be in the schema from the start

---

### Pitfall 8: Portal-Specific Bot Detection / Rate Limiting

**What goes wrong:** One or more government portals blocks the scraper after a few weeks of nightly runs. The scraper's requests pattern (same User-Agent, same timing, same IP, same request order every night at 2:00 AM) is flagged. The portal starts returning 403s, CAPTCHAs, or empty pages. The scraper doesn't crash — it just extracts nothing and moves on.

**Why it happens:** Even government portals have Cloudflare or basic bot protection. Headless Chromium is increasingly fingerprint-detectable in 2025-2026. A fixed nightly schedule from a single EC2 IP is a recognizable pattern.

**Prevention:**
- Randomize scrape timing within a window (run portals in random order, add 1-5 second jitter between requests)
- Set realistic browser fingerprints: proper User-Agent strings, viewport sizes, and browser feature flags
- Implement per-portal configurable delays; for sensitive portals, use 10-15 seconds between page requests
- Check robots.txt for each portal at setup time and respect Crawl-delay directives
- Monitor HTTP response codes per portal in the audit log; alert on sustained 403/429 rates

**Warning signs:**
- A portal suddenly returning 0 listings after weeks of normal operation
- HTTP 403 or 429 response codes appearing in scraper logs
- Pages loading but containing CAPTCHA markup rather than listing content

**Phase to address:** Phase 1 (scraper design) — build rate limiting and jitter from the start; retrofitting is painful

---

### Pitfall 9: Single EC2 as Single Point of Failure for Nightly Jobs

**What goes wrong:** The EC2 instance reboots (AWS maintenance, spot instance termination, kernel update), and Docker Compose doesn't restart containers automatically. The cron job that triggers the nightly scrape is inside a container that didn't restart. Listings silently stop updating. No one notices for 3-5 days until a BD team member checks and finds stale data.

**Why it happens:** Docker Compose `restart: unless-stopped` only applies to long-running services. One-off scraper jobs triggered by cron don't have automatic retry semantics. EC2 instance state is ephemeral unless explicitly managed.

**Prevention:**
- Use `restart: always` for all persistent services (PostgreSQL, Next.js)
- Use an external cron trigger (AWS EventBridge rule invoking an SSM command or Lambda) rather than an in-container cron — this survives container restarts
- Alternatively: run the scraper as a systemd service on the EC2 host with `Restart=on-failure`
- Add a dead-man's switch: a monitoring check that alerts if no new listings have been inserted in 26+ hours (more than one nightly cycle)
- Store last-successful-run timestamp in the database; expose it on the dashboard

**Warning signs:**
- "Last updated" timestamp on the dashboard stuck on the same date
- Zero new listings added in 24+ hours across all portals

**Phase to address:** Phase 2 (deployment) — set up monitoring before declaring the system "live"

---

### Pitfall 10: pgvector Index Not Built Until Scale Forces a Rebuild

**What goes wrong:** During development and early production with a few thousand listings, vector search works fine without an index (sequential scan). At 20,000-50,000 listings, queries become slow (multi-second). Adding an HNSW or IVFFLAT index at that scale requires a blocking table rewrite and takes significant time. Meanwhile, production search is unusably slow.

**Why it happens:** pgvector sequential scans work fine at low cardinality and mask the need for indexing. Teams build without an index and don't test at production data volumes.

**Prevention:**
- Create the HNSW index in the initial schema migration, before any data is inserted: `CREATE INDEX USING hnsw (embedding vector_cosine_ops)`
- Size the index parameters for expected scale: with 50,000 listings, `m=16, ef_construction=64` is a good baseline
- Run a load test with synthetic data at 10x expected volume before going live
- Monitor query time for semantic search; alert if p95 exceeds 500ms

**Warning signs:**
- Semantic search response time increasing linearly with database size
- `EXPLAIN ANALYZE` showing `Seq Scan` on the embeddings column at scale

**Phase to address:** Phase 2 (database schema) — index creation is trivial upfront, painful retroactively

---

## Minor Pitfalls

---

### Pitfall 11: "Works in Dev" Playwright vs Production Docker Differences

**What goes wrong:** Playwright works perfectly locally (macOS, Chrome installed). In the Docker container on EC2, it fails due to missing system dependencies (libglib, libnss, libexpat), wrong Chromium binary path, or mismatched Playwright version vs browser binary. Results in hours of environment debugging on first deploy.

**Prevention:**
- Use the official `mcr.microsoft.com/playwright/python` base image rather than installing Playwright on top of a generic Python image
- Pin the exact Playwright version in requirements.txt; never use `playwright install` without a version specifier in Docker builds
- Test the Docker image locally with `docker compose up` before pushing to EC2

**Phase to address:** Phase 1 (Docker setup)

---

### Pitfall 12: Unstructured Text Search vs. Semantic Search Confusion

**What goes wrong:** PostgreSQL full-text search (tsvector/tsquery) and pgvector semantic search are both deployed but do different things. SQL filtering uses exact keyword matching. Semantic search uses embedding similarity. If they're not combined correctly (hybrid search), users get inconsistent results: a keyword search for "IT consulting" returns listings where pgvector semantic search would have found "information technology services." Users conclude the search is broken.

**Prevention:**
- Implement hybrid search from the start: combine pgvector cosine similarity with PostgreSQL full-text search using a weighted score
- Use `ts_rank` for keyword relevance + vector similarity for semantic relevance; blend with a tunable weight (0.6 vector + 0.4 keyword is a reasonable baseline)
- Clearly document for users which search mode is being used and what to expect

**Phase to address:** Phase 2 (search implementation)

---

### Pitfall 13: No Scrape Run Audit Trail

**What goes wrong:** Something goes wrong with a nightly run (wrong data extracted, a portal errored, a portal was skipped). Without a `scrape_runs` table recording run metadata, there's no way to investigate: which portals ran? How many listings did each return? What was the error? Teams end up debugging by guessing.

**Prevention:**
- Create a `scrape_runs` table: `(id, portal_id, started_at, completed_at, listings_found, listings_new, listings_updated, error_message, status)`
- Log every portal's outcome regardless of success/failure
- Expose a `/admin/scrape-runs` page on the dashboard showing the last 7 days of run history per portal

**Phase to address:** Phase 1 (data schema)

---

### Pitfall 14: Terraform State Stored Locally

**What goes wrong:** Terraform state is stored in a local `terraform.tfstate` file, committed accidentally to git (leaking AWS credentials/resource IDs), or lost when a developer's laptop is wiped. Next infrastructure change requires manual state reconstruction.

**Prevention:**
- Configure remote state in S3 + DynamoDB locking from the very first `terraform init`
- Add `terraform.tfstate` and `terraform.tfstate.backup` to `.gitignore` before any `terraform apply`
- Use a dedicated Terraform IAM role with minimum required permissions

**Phase to address:** Phase 1 (infrastructure setup)

---

## Technical Debt Patterns

Patterns that seem fine initially but compound into expensive problems.

| Pattern | What It Becomes | Prevention |
|---------|----------------|------------|
| Hardcoding portal-specific extraction logic | Each new portal requires code changes; schema can't represent differences | Store portal configs in DB; extraction instructions are data, not code |
| Using `image: latest` in docker-compose.yml | Silent breaking changes when base images update | Pin specific image digests or version tags in production compose file |
| Single PostgreSQL connection without pooling | Connection exhaustion under concurrent scraper + frontend load | Add PgBouncer or use asyncpg connection pool from the start |
| Storing raw HTML in PostgreSQL | Storage explosion (HTML is 10-100x the size of extracted text) | Store only extracted fields + URL reference; archive raw HTML to S3 if needed |
| Per-listing API calls to the embedding model | Rate limits hit at scale; single slow call blocks the pipeline | Batch embedding API calls (OpenAI supports up to 2048 items per batch) |

---

## Integration Gotchas

Specific to the Browser Use + LangExtract + pgvector + Next.js stack.

### Browser Use + Playwright Interaction
Browser Use wraps Playwright but adds its own session management. Using both Browser Use's managed browser AND raw Playwright in the same scraper causes context conflicts. Pick one: either use Browser Use for AI-driven navigation AND simple Playwright for stable portals, but keep them in separate processes.

### LangExtract Grounding Requirements
LangExtract's source grounding works on plain text, not on raw HTML. The page must be cleaned to text before passing to LangExtract. If you pass HTML, character offsets in grounding spans are meaningless for validation. Build an HTML-to-text cleaning step (BeautifulSoup or trafilatura) between Playwright extraction and LangExtract.

### pgvector + Next.js Direct Connection
Next.js API routes open a new database connection per request in serverless mode. With pgvector, each connection loads the extension. On a single EC2 with Docker Compose, Next.js runs as a persistent process, but this should still use a connection pool (Prisma's built-in pool or PgBouncer) to prevent connection storms when multiple users hit the dashboard simultaneously.

### CanadaBuys API vs. Scraping
CanadaBuys (the federal procurement portal that replaced buyandsell.gc.ca in 2022) may expose API endpoints. Check before building a full browser scraper for it — an official API is far more reliable than scraping and less likely to break on layout changes. Using the API for federal listings and browser scraping only for portals with no API reduces fragility significantly.

---

## Performance Traps

| Concern | At 5,000 listings | At 50,000 listings | At 500,000 listings |
|---------|-------------------|--------------------|--------------------|
| pgvector semantic search | Seq scan: 50ms | Without index: 5-10s | Index required, RAM pressure |
| PostgreSQL full-text index | Fine | Fine | Consider partitioning by date |
| Nightly embedding generation | ~5 min for 200 new listings | ~50 min if re-embedding all | Must be incremental (only new/changed) |
| EC2 instance size (t3.medium) | Adequate | RAM pressure at peak | Upgrade to t3.large/xlarge |
| Docker Compose log volume | Negligible | GB/week without log rotation | Add logrotate config |

---

## Security Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Hardcoding LLM API keys in docker-compose.yml | Key exposed in git history | Use AWS Secrets Manager or environment files outside the repo |
| PostgreSQL exposed on public EC2 interface | Database accessible from internet | Bind PostgreSQL to 127.0.0.1 only; access via Docker network |
| Next.js admin routes without auth check | Scrape run data, portal configs exposed | Apply authentication middleware to all `/admin/*` routes |
| Browser Use executing on untrusted page content | Prompt injection from malicious portal content | Sanitize all page text before passing to LLM; don't let page content influence system prompts |
| Terraform outputs containing secrets in CI logs | Credentials in CI output | Use `sensitive = true` on all secret outputs in Terraform |

---

## "Looks Done But Isn't" Checklist

Before declaring the platform production-ready, verify each item:

- [ ] Nightly job alert fires if zero new listings inserted in 26+ hours
- [ ] Per-portal yield tracking visible on a dashboard page
- [ ] All dates stored as `TIMESTAMPTZ` with correct timezone normalization
- [ ] Semantic search tested with 20 real procurement queries from the BD team (not synthetic queries)
- [ ] LLM extraction validated against manually-checked listings from 5+ representative portals
- [ ] Token cost per nightly run measured and projected for 30/60/90 days
- [ ] HNSW index created before data reaches 10,000 listings
- [ ] Browser processes close cleanly after each portal (no zombie process accumulation)
- [ ] EC2 memory usage monitored with CloudWatch alarm at 80%
- [ ] Docker Compose production file (`docker-compose.prod.yml`) separate from dev config
- [ ] Terraform remote state configured in S3 before first `terraform apply`
- [ ] PostgreSQL not accessible on public EC2 interface
- [ ] CanadaBuys API investigated before building a full browser scraper for federal listings
- [ ] robots.txt checked for each of the 63 portals and compliance documented

---

## Pitfall-to-Phase Mapping

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Data schema design | Missing TIMESTAMPTZ, no upsert keys, no audit table | Design `TIMESTAMPTZ`, composite unique constraints, and `scrape_runs` table before writing any data |
| First scraper built | LLM hallucination undetected, no validation | Add post-extraction field validation in the same phase as extraction code |
| Docker infrastructure | Playwright /dev/shm crash, zombie browsers | Configure `shm_size`, `mem_limit`, and `try/finally` cleanup in Phase 1 |
| Scaling to all 63 portals | LLM API cost explosion, memory exhaustion | Benchmark cost on 5 representative portals before enabling all 63 |
| pgvector + search | No index at scale, embedding model lock-in | Create HNSW index in initial schema; document model choice as a locked decision |
| EC2 deployment | Single point of failure, no dead-man monitoring | Set up CloudWatch alarm and dead-man check before calling system "live" |
| Nightly job reliability | Silent per-portal failures, cron not restarting | Use external scheduler (EventBridge) + per-portal yield alerting |
| Search quality | Keyword vs. semantic confusion, wrong results | Implement hybrid search; validate with real BD team queries |
| Operations | No audit trail, undetectable degradation | `scrape_runs` table + dashboard page in Phase 2 |

---

## Sources

- [Patterns and Anti-Patterns in Web Scraping — Browserless](https://www.browserless.io/blog/patterns-and-anti-patterns-in-web-scraping)
- [Stop Getting Blocked: 10 Common Web-Scraping Mistakes — Firecrawl](https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes)
- [Why Web Scraping Works in Testing but Fails in Production — Grepsr](https://www.grepsr.com/blog/web-scraping-testing-vs-production/)
- [Why Scraped Data Quietly Becomes Unreliable — Medium](https://medium.com/@goatishfw/why-scraped-data-quietly-becomes-unreliable-before-anyone-notices-536218e5276f)
- [Playwright Memory Issues — GitHub Issues](https://github.com/microsoft/playwright/issues/15400)
- [Playwright on AWS EC2 — Browserless](https://www.browserless.io/blog/playwright-on-aws-ec2)
- [Stop Misusing Docker Compose in Production — dFlow](https://dflow.sh/blog/stop-misusing-docker-compose-in-production-what-most-teams-get-wrong)
- [The Case Against pgvector — Alex Jacobs](https://alex-jacobs.com/posts/the-case-against-pgvector/)
- [Hybrid Search in PostgreSQL: The Missing Manual — ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Scaling Semantic Search with pgvector — pgconf.in](https://pgconf.in/files/presentations/2025/954.pdf)
- [When Good Models Go Bad — Weaviate](https://weaviate.io/blog/when-good-models-go-bad)
- [Introducing LangExtract — Google Developers Blog](https://developers.googleblog.com/introducing-langextract-a-gemini-powered-information-extraction-library/)
- [LangExtract GitHub — google/langextract](https://github.com/google/langextract)
- [Reducing Hallucinations in LLM Data Extraction — DEV Community](https://dev.to/parthex/reducing-hallucinations-when-extracting-data-from-pdf-using-llms-4nl5)
- [Stop Silent Failures: Using LLMs to Validate Scraper Output — DEV Community](https://dev.to/anderecit/stop-silent-failures-using-llms-to-validate-web-scraper-output-24gf)
- [Agentic AI Browsers in 2025: Navigating Promise and Pitfalls — AI 2 Work](https://ai2.work/technology/ai-tech-agentic-ai-browsers-tested-2025/)
- [Web Scraping Legal Issues: 2025 Enterprise Compliance Guide — GroupBWT](https://groupbwt.com/blog/is-web-scraping-legal/)
- [Data Deduplication and Canonicalization in Scraped Knowledge Graphs — ScrapingAnt](https://scrapingant.com/blog/data-deduplication-and-canonicalization-in-scraped)
- [Canada's Government Electronic Tendering Service — CanadaBuys](https://buyandsell.gc.ca/procurement-data/gets-on-canadabuys-4)
- [The Hidden Cost of LLM APIs — SOO Group](https://thesoogroup.com/blog/hidden-cost-of-llm-apis-token-economics)
- [Browser Use — Fastest Web Agent (LLM Gateway post)](https://browser-use.com/posts/llm-gateway)
