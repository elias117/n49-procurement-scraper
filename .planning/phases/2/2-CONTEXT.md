# Phase 2 Context: Scraper Pipeline

**Phase Goal:** The scraper runs manually against all 63 portals, populates listings into PostgreSQL with valid structured fields and embeddings, and logs per-portal audit data — ready to be queried.

**Requirements:** SCRP-01, SCRP-02, SCRP-03, SCRP-04, SCRP-05, SCRP-06

---

## 0. Browser Environment (POC Finding — Hard Requirement)

### headless=True Gets Blocked
- **`headless=True` gets 403-blocked** on portals like CanadaBuys. This is a hard blocker.
- Procurement portals detect headless Chromium and return 403 Forbidden.
- This was confirmed during the POC — not theoretical.

### Solution: Xvfb (X Virtual Framebuffer)
- Run Chromium with **`headless=False`** inside Docker.
- Use **Xvfb** to provide a virtual display so Chromium thinks it has a real screen.
- The Dockerfile must install `xvfb` and the entrypoint must wrap the scraper command with `xvfb-run`.
- `shm_size: '2gb'` is already in docker-compose.yml (required for Chromium).

### Docker Requirements
- `apt-get install -y xvfb` in the Dockerfile
- Entrypoint: `xvfb-run python main.py` (not `python main.py` directly)
- All browser-use Agent instances must use `headless=False`
- Config: `BROWSER_HEADLESS = False` (not True)

---

## 1. Extraction Quality Bar

### Minimum Viable Listing
- **Title + source URL + source portal** — that's the floor. Enough to click through and evaluate.
- Description is nice but not required — some portals put everything in the title.
- Closing date is important but not a gate — standing offers and supply arrangements have no fixed close date.

### Missing Fields Policy
- **Always show the listing.** Never hide a listing because of missing metadata.
- Missing fields stored as null, displayed as "Not specified" in the UI.
- The BD team decides relevance — the system just surfaces what's there.

### Dollar Values
- Completely normal to be missing. Most government postings don't publish values.
- Not a quality problem — leave value fields null and show the listing.

### AI Guesses vs Blank
- **Blank is always better than a wrong guess** for structured fields.
- Never guess: NAICS/UNSPSC/GSIN codes, dollar values, closing dates.
- A wrong NAICS code means the listing appears in the wrong filter and someone misses it in the right one.
- A wrong closing date is actively dangerous — someone could think they have time when they don't.
- Extract only what's clearly stated in the source. Leave everything else null.
- The `completeness_score` field surfaces well-populated listings naturally.

---

## 2. Portal Failure & Staleness

### Failure Tolerance
- When a portal fails on a run, its existing listings **stay visible** in search.
- Listings are flagged with a freshness indicator based on the portal's `last_scraped_at`.

### Staleness Thresholds
- **1 missed night:** Noise. No visual indicator.
- **3 consecutive failures:** Amber flag on health page. Something is actually broken.
- **7+ days stale:** Red flag. Urgent attention needed.

### Auto-Disable
- After **5 consecutive failures**, auto-set `enabled = false` on the portal.
- Log the disable event. No point burning LLM credits on a broken portal every night.
- Health page shows portal as "disabled by failure" — manual re-enable required after investigation.

### Closed Listings
- Keep all past-closing-date listings in the database indefinitely.
- Default search filter excludes them (show open/future only — already in Phase 3/4 spec).
- Dashboard provides "Include closed listings" toggle for competitive intelligence and spotting reposted opportunities.

---

## 3. Federal Procurement Source (CanadaBuys)

### API over Scraping
- **Use the CanadaBuys API** for federal listings. No question.
- More reliable, returns structured JSON, zero LLM cost.
- API sources bypass Browser Use (Stage 1) and LangExtract (Stage 4) entirely.
- The pipeline architecture already supports alternate ingestion paths.

### Data Completeness
- Federal listings via API will naturally have more complete fields than scraped portals.
- Nobody cares about cross-portal consistency — the BD team cares about finding opportunities.
- `completeness_score` handles this naturally.

### Other API Sources
- **Investigate SEAO (Quebec)** — has an open data feed.
- SAP Ariba-based portals sometimes expose structured data — check opportunistically.
- Build the API ingestion path for CanadaBuys now; add others if discovered during Phase 2 work.

### Filtering Strategy
- **Pull everything** from CanadaBuys. Do not filter at the API level.
- The 111-keyword library handles relevance scoring at the application layer.
- Restricting at the API risks missing opportunities that don't match commodity codes but are relevant by description.
- Storage is cheap — cast a wide net, filter in the dashboard.

---

## 4. Cross-Portal Duplicates

### No Dedup in v1
- **Separate listings.** Each portal source creates its own listing record.
- Merging risks hiding distinct opportunities. Fuzzy matching across portals is unreliable.
- Cross-posting is low frequency (~5-10% of listings), mainly federal contracts appearing on aggregators.

### No Cross-Portal Linking in v1
- Visual linking ("Also posted on: CanadaBuys") is a v2 feature.
- Requires embedding similarity matching across listings — adds processing overhead and edge cases.

### No "Best Field" Merging
- Show both listings independently. Let the BD team click through and compare.
- "Best field" merging creates Frankenstein listings where no single source URL is authoritative.

---

## Deferred Ideas

*(Captured during discussion — not in Phase 2 scope)*

- Cross-portal duplicate linking / visual "Also posted on" indicators (v2)
- "Best field" merging across portal sources
- API ingestion for SEAO and SAP Ariba portals (opportunistic — investigate but don't block on)
- Filtering at API source level (rejected — filter at app layer instead)

---

## Existing Concerns (from STATE.md)

These were flagged during Phase 1 and should be addressed during Phase 2 research/planning:

1. **CanadaBuys API** — RESOLVED: Use the API, not browser scraping.
2. **LLM API cost benchmarking** — Still open. Benchmark on 5 representative portals before enabling all 63.
3. **robots.txt compliance** — Still open. Audit all 63 portals before enabling full set in production.

---

*Created: 2026-02-24 via phase discussion*
