# Feature Landscape

**Domain:** Procurement Intelligence / Government Contract Search (Canadian, Internal BD Tool)
**Researched:** 2026-02-24
**Overall Confidence:** HIGH (confirmed by multiple competitive platforms, Canadian portal research, and BD workflow analysis)

---

## Context

This is an **internal BD team tool**, not a SaaS product. The team monitors 63 Canadian government procurement portals. The adoption bar is low: if listings populate nightly and search works, the team uses it daily. Feature decisions must be filtered through this lens — features that would be table stakes for a SaaS product are anti-features for an internal tool if they add complexity without direct BD value.

---

## Table Stakes

Features the BD team expects. Missing = platform feels broken or useless. These are confirmed as standard across all comparable platforms (MERX, CanadaBuys, GCFinder, Sweetspot, Tendium).

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Keyword search** | Cannot find opportunities without it; every portal has this | Low | Full-text across title + description minimum |
| **Filter: closing date range** | Deadlines are the primary time constraint for BD; expired opportunities are worthless | Low | Must show open-only by default; future-dated closing dates |
| **Filter: source portal** | Team needs to know provenance; "where did this come from?" is always asked | Low | Dropdown or checkbox, all 63 portals |
| **Filter: region / province** | Canadian procurement is regionally structured; team focuses on specific regions | Low | Province-level minimum; maps to portal metadata |
| **Filter: category / commodity code** | NAICS, UNSPSC, GSIN — standard classification by which opportunities are scoped | Medium | Multiple code systems; values extracted by AI scraper |
| **Filter: estimated contract value** | Team skips contracts below threshold; large contracts get priority review | Low | Range slider or min/max inputs; extracted field may be null |
| **Filter: solicitation type** | RFP vs RFQ vs RFI vs Standing Offer have different response requirements | Low | Dropdown; extracted from listing metadata |
| **Filter: posting date** | Team needs to see what's new since last visit | Low | "Posted in last N days" is common pattern |
| **Listing detail view** | Full structured data for a single opportunity; team reads this to evaluate | Low | All extracted fields displayed cleanly |
| **Pagination / results browsing** | Volume is 1,000–5,000 listings; cannot display all at once | Low | Standard pagination or infinite scroll |
| **Sort by: closing date (ascending)** | Default expectation; most urgent first | Low | Also sort by posting date, relevance |
| **Data freshness indicator** | Team must trust the data; knowing "last scraped: 11pm last night" builds confidence | Low | Per-listing or per-portal timestamp visible |
| **Link to source portal** | Team may need to download documents, register to bid — must go to origin | Low | Clickable link to canonical source URL |
| **Authentication (simple login)** | Internal tool; no public access | Low | Username/password sufficient; PROJECT.md confirms OAuth/SSO out of scope |
| **Natural language search** | Explicitly required in PROJECT.md; team uses queries like "construction contracts expiring next month in Ontario" | High | pgvector semantic search; must work alongside keyword filters |

---

## Differentiators

Features that elevate this platform above manually checking portals or using basic aggregators. Not expected from day one, but add significant BD value and justify internal investment.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Unified search across all 63 portals simultaneously** | The entire value of this platform vs. manual checking; no comparable free Canadian tool does this comprehensively | High | Already the core product premise; the scraper pipeline makes this possible |
| **AI-structured field extraction** | Raw portal HTML rarely has clean structured data; AI extraction means consistent fields across all 63 portals | High | LangExtract does this; enables reliable filtering |
| **Amendment history per listing** | Portals update listings; knowing "this RFP was amended twice" is relevant signal for bid/no-bid decisions | Medium | Track changes over time; display version history |
| **Saved searches (persistent filters)** | Team members return daily; typing the same filters each visit is friction | Medium | Named saved search profiles per user; run on demand |
| **"New since last visit" or "New today" badge** | BD team's daily workflow: "what's new?" not "what exists?" | Low-Medium | Track last-login timestamp; badge new listings |
| **Scraper run status / health dashboard** | Team needs to know if a portal failed to scrape last night; data gaps cause missed opportunities | Medium | Simple admin view: per-portal last-run status, success/fail, listing count |
| **Document attachment listing** | Many RFPs link to PDFs/SOW docs; showing that attachments exist (with links) saves portal round-trips | Low | Extract and surface document URLs from listings |
| **Opportunity "flag" or "bookmark"** | BD team member marks an opportunity for follow-up or assigns to a colleague | Low | Simple bookmark per-user; not full pipeline management |
| **Contact information display** | Structured contact (name, email, phone) extracted and displayed removes a portal visit | Low | Extracted field; display when available |
| **Deduplication across portals** | Some listings appear on multiple portals (e.g., federal on CanadaBuys + MERX); showing duplicates wastes review time | High | Fuzzy match on title + buyer + closing date; complex to get right |
| **Combined keyword + semantic search** | Neither pure keyword nor pure vector search alone is sufficient; hybrid retrieval gives best relevance | High | pgvector + tsvector hybrid; requires careful query routing |

---

## Anti-Features

Features to deliberately NOT build in v1. Confirmed out of scope by PROJECT.md, or identified as scope creep traps from competitor analysis.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Email alerts / saved search notifications** | PROJECT.md explicitly defers to v2; adds email infrastructure complexity (SMTP, unsubscribe, bounce handling) for marginal gain when team visits dashboard daily | Saved searches the team runs manually on login |
| **Bid/no-bid scoring / win probability** | Requires historical award data, ML models, calibration; platforms like Sweetspot and Procurement Sciences spend years on this; premature for v1 | Let the BD team make this judgment call themselves |
| **Proposal writing / AI drafting** | Completely out of scope for an opportunity discovery tool; scope creep from GovCon SaaS platforms | Out of scope; separate concern |
| **CRM / pipeline management** | Capture2Proposal and GovDash build full pipeline tools; an internal discovery tool doesn't need Salesforce features | A simple bookmark/flag per listing is sufficient |
| **OAuth / SSO / RBAC** | Small internal team; PROJECT.md confirms simple auth is sufficient | Username + password auth |
| **Mobile app** | PROJECT.md out of scope; team works at desks reviewing opportunities | Responsive web layout is acceptable minimum |
| **Real-time scraping** | PROJECT.md confirms nightly is sufficient; real-time adds queue infrastructure complexity | Nightly batch with timestamp transparency |
| **Multi-tenant / organization management** | Single internal team; SaaS features add architectural complexity with no benefit | Single-tenant |
| **Analytics dashboards / spend analysis** | Not a spend management tool; scope creep from enterprise procurement platforms | Surface data inline with listings, not separate analytics |
| **Competitor intelligence / vendor tracking** | Sweetspot/GovDash features for tracking who won contracts; not the use case here | Out of scope v1 |
| **Browser extension** | GCFinder offers this for SAM.gov; makes no sense when all 63 portals are already aggregated | The dashboard IS the aggregation layer |
| **Compliance matrix / RFP shredding** | Proposal support feature; not opportunity discovery | Out of scope |
| **Per-portal scraping configuration UI** | Building an admin GUI for scrapers is a product in itself; the 63 portals are a known fixed set | Configure scrapers in code; not a user-facing feature |

---

## Feature Dependencies

```
Authentication → Everything (no unauthenticated access)

Scraper pipeline (nightly) → Listings in DB → All search/filter features

Structured field extraction (AI) → Filter: category codes
Structured field extraction (AI) → Filter: contract value
Structured field extraction (AI) → Contact information display
Structured field extraction (AI) → Document attachment listing
Structured field extraction (AI) → Solicitation type filter

pgvector embeddings → Natural language search
pgvector embeddings → Combined hybrid search
PostgreSQL full-text index → Keyword search

Keyword search → Combined keyword + semantic search (hybrid)
Natural language search → Combined keyword + semantic search (hybrid)

Listing detail view → Amendment history (detail view displays history)
Listing detail view → Document attachment listing (shown in detail view)

Saved searches → "New since last visit" badges (saved search timestamps enable this)

Scraper run status → Data freshness indicator (status feeds the indicator)
```

---

## MVP Recommendation

The MVP must answer one question for the BD team: "What new government opportunities posted since yesterday are relevant to us?"

**Prioritize for v1:**

1. **Nightly scraping + structured extraction** — The entire platform collapses without this. Ship nothing until data populates reliably.
2. **Keyword search + core filters** (closing date, region, portal source, posting date, solicitation type) — This alone beats manual portal checking.
3. **Natural language search** — Explicitly required; pgvector is already in the stack.
4. **Listing detail view with source link** — Team must be able to read the full listing and navigate to the portal to act.
5. **Data freshness indicator + scraper status** — Trust is fragile; team must know when data is stale.
6. **Simple authentication** — Required for any internal deployment.
7. **"New today" / "New since last visit" badges** — Daily-use tool; this is the hook that makes it habitual.

**Defer to v2:**
- Email alerts (PROJECT.md confirms out of scope)
- Saved search profiles (useful but not blocking adoption)
- Amendment history (nice signal, moderate effort)
- Deduplication (complex to get right; tolerate duplicates in v1)
- Bookmarks/flags (low effort, but validate daily use first)

---

## Prioritization Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Nightly scraper pipeline | Critical | High | P0 — Blocking |
| AI field extraction | Critical | High | P0 — Blocking |
| Keyword search | Critical | Low | P0 |
| Filter: closing date | Critical | Low | P0 |
| Filter: region / province | High | Low | P0 |
| Filter: portal source | High | Low | P0 |
| Listing detail view | Critical | Low | P0 |
| Source URL link | Critical | Low | P0 |
| Authentication | Critical | Low | P0 |
| Data freshness indicator | High | Low | P0 |
| Natural language search | High | Medium | P0 (in stack) |
| Filter: category / codes | High | Low-Medium | P1 |
| Filter: contract value | Medium | Low | P1 |
| Filter: solicitation type | Medium | Low | P1 |
| Sort controls | Medium | Low | P1 |
| "New today" badge | High | Low | P1 |
| Scraper health dashboard | High | Medium | P1 |
| Document attachment links | Medium | Low | P1 |
| Contact info display | Low | Low | P1 |
| Hybrid search (keyword + semantic) | High | Medium | P1 |
| Saved searches | Medium | Medium | P2 |
| Bookmarks / flags | Medium | Low | P2 |
| Amendment history | Medium | High | P2 |
| Deduplication across portals | Medium | High | P2 |
| Email alerts | Low | High | v2 |
| Bid/no-bid scoring | Low | Very High | v2+ |
| Pipeline / CRM features | Low | Very High | Never (wrong tool) |

---

## Sources

- MERX search filter documentation: https://www.merx.com/resources/articles/using-the-search-filters-to-find-matching-tenders
- Sweetspot feature set: https://www.sweetspot.so/ (government contracting AI platform)
- GCFinder feature set: https://govcontractfinder.com/
- Tendium tender monitoring: https://tendium.ai/en/tender-monitoring/
- Mercell tender monitoring guide: https://info.mercell.com/en/procurement-insights/tender-monitoring-guide/
- Publicus.ai Canadian procurement AI: https://publicus.ai/newsletter/government-procurement-ai-for-municipal-vendors
- Capture2Proposal BD features: https://capture2proposal.com/bd-persona/
- GovDash features: https://www.govdash.com/
- CanadaBuys portal context: https://canadabuys.canada.ca/en/other-tendering-websites
- GovCon BD pain points / too many portals: https://iquasar.com/blog/5-government-contract-opportunity-search-tools/
- Suplari top procurement intelligence platforms: https://suplari.com/blog/top-procurement-intelligence-platforms/
- GovSpend B2G intelligence: https://govspend.com/
