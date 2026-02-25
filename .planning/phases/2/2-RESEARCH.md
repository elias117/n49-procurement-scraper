# Phase 2: Scraper Pipeline - Research

**Researched:** 2026-02-24
**Domain:** AI-powered web scraping, structured data extraction, federal open data, embeddings
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 builds the scraper pipeline that runs against all 63 procurement portals, extracting structured listing data into PostgreSQL with embeddings. The pipeline has three distinct ingestion paths: (1) CanadaBuys via CSV open data files -- no browser or LLM needed, (2) BidsAndTenders platform portals (~20 subdomains) via browser-use navigation + LLM extraction, and (3) remaining diverse portals via browser-use navigation + LLM extraction. Browser Use (v0.11.x) handles AI-driven browser navigation with Playwright underneath, while LangExtract (v1.1.1) or alternatively the `instructor` library handles structured field extraction from page content using OpenAI models. OpenAI `text-embedding-3-small` generates 1536-dimensional embeddings at $0.02/1M tokens.

The biggest cost driver is the LLM extraction step. Using GPT-4o-mini ($0.15/1M input, $0.60/1M output), a typical portal page of ~5K tokens costs roughly $0.001 per listing extraction. At 3,000 listings/night, that is approximately $3-5/night for extraction. Browser Use's own LLM model (`ChatBrowserUse`) costs $0.20/1M input and $2.00/1M output, used only for navigation steps. CanadaBuys ingestion via CSV has zero LLM cost. The total nightly cost estimate is $5-15 depending on portal complexity and navigation steps required.

**Primary recommendation:** Use Browser Use for navigation only (get to the right pages, handle pagination), then extract raw HTML via Playwright's `page.content()`, and feed that HTML into an LLM-based structured extraction step using `instructor` with GPT-4o-mini and Pydantic models. CanadaBuys bypasses all of this with direct CSV download.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Blank is always better than a wrong guess for structured fields
- Never guess: NAICS/UNSPSC/GSIN codes, dollar values, closing dates
- CanadaBuys: use API/open data not browser scraping
- Pull everything from CanadaBuys (no API-level filtering)
- Auto-disable portal after 5 consecutive failures
- 111-keyword library handles relevance scoring at app layer
- text-embedding-3-small is the locked embedding model
- Each portal source creates its own listing record (no cross-portal dedup)
- Keep all past-closing-date listings indefinitely
- Minimum viable listing: title + source URL + source portal
- Missing fields stored as null, displayed as "Not specified"
- Staleness thresholds: 1 night = noise, 3 failures = amber, 7+ days = red
- After 5 consecutive failures, auto-set enabled = false

### Claude's Discretion
- Pipeline architecture and concurrency model
- Choice of LLM model for extraction (within OpenAI ecosystem)
- BidsAndTenders scraping approach (common handler vs per-portal)
- Error handling and retry strategy
- robots.txt compliance approach
- Whether to use LangExtract or an alternative for structured extraction

### Deferred Ideas (OUT OF SCOPE)
- Cross-portal duplicate linking / visual "Also posted on" indicators (v2)
- "Best field" merging across portal sources
- API ingestion for SEAO and SAP Ariba portals (opportunistic -- investigate but do not block on)
- Filtering at API source level (rejected -- filter at app layer instead)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCRP-01 | Scraper pipeline runs nightly against all 63 mapped portals | Pipeline architecture, concurrency model, portal registry, CanadaBuys CSV + browser-use patterns |
| SCRP-02 | AI-powered extraction produces structured fields per listing | LangExtract/instructor for extraction, Pydantic schemas, GPT-4o-mini for parsing |
| SCRP-03 | Each scrape run logs per-portal results to scrape_runs audit table | Database patterns, error isolation, scrape_runs table already exists |
| SCRP-04 | Post-extraction validation rejects invalid data | Pydantic validation, date logic, "blank over wrong guess" policy |
| SCRP-05 | Embeddings generated at insert time using text-embedding-3-small | OpenAI embeddings API, batch processing, cost model |
| SCRP-06 | Listings upserted on composite key | PostgreSQL ON CONFLICT DO UPDATE, psycopg2 execute_values |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| browser-use | 0.11.x | AI browser navigation (Playwright-based) | Best-in-class AI browser automation; handles diverse portal layouts without per-site selectors |
| instructor | 1.x | Structured LLM extraction with Pydantic | Lightweight, OpenAI-native, Pydantic validation with auto-retry; simpler than LangExtract for our use case |
| openai | 1.x | Embeddings API + LLM extraction backend | Already in stack for embeddings; instructor wraps it for extraction |
| psycopg2-binary | 2.9.10 | PostgreSQL driver | Already installed in Phase 1 stub |
| playwright | 1.51.0 | Browser engine (bundled with Docker image) | Already in Dockerfile base image |
| pydantic | 2.x | Schema definition and validation | Industry standard for Python data validation |
| httpx | 0.27.x | HTTP client for CanadaBuys CSV download | Async-capable, modern Python HTTP client |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tiktoken | 0.x | Token counting for embeddings | Pre-check text length before embedding API calls |
| beautifulsoup4 | 4.x | HTML parsing/cleaning | Strip HTML to text before LLM extraction to reduce tokens |
| robotexclusionrulesparser | 0.x | robots.txt compliance | Check each portal's robots.txt before scraping |
| tenacity | 8.x | Retry logic with backoff | Wrap API calls and browser operations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| instructor | LangExtract | LangExtract is Gemini-oriented, uses few-shot examples rather than Pydantic schemas, heavier dependency; instructor is OpenAI-native and lighter |
| instructor | Direct OpenAI function calling | Instructor adds retry logic and Pydantic validation on top; worth the thin wrapper |
| httpx | requests | httpx supports async; useful if we want parallel CSV downloads later |
| browser-use | Raw Playwright | browser-use handles diverse layouts with AI; raw Playwright would need per-portal selectors |

**Installation:**
```bash
pip install browser-use instructor openai psycopg2-binary pydantic httpx tiktoken beautifulsoup4 tenacity
pip install robotexclusionrulesparser
```

**Why instructor over LangExtract:** The project chose LangExtract in the initial design. However, research reveals LangExtract (v1.1.1) was released by Google in August 2025, is primarily designed around Gemini models, and uses a few-shot example approach rather than Pydantic schemas. Our project already depends on OpenAI (for embeddings) and needs simple Pydantic-based extraction. The `instructor` library (by Jason Liu, widely adopted) is a thin wrapper around OpenAI's function calling that adds Pydantic validation and automatic retries -- a much better fit. LangExtract would work but adds unnecessary complexity and a second LLM provider dependency. If the user prefers LangExtract, it can work with `pip install langextract[openai]` and `fence_output=True`, but instructor is the stronger recommendation.

## Architecture Patterns

### Recommended Project Structure
```
scraper/
  main.py                    # CLI entrypoint (run all, run one portal, etc.)
  config.py                  # Settings, env vars, constants
  db.py                      # Database connection pool, upsert helpers
  models.py                  # Pydantic models for listings, extraction schemas
  pipeline/
    __init__.py
    orchestrator.py           # Main loop: iterate portals, dispatch to handlers
    canadabuys.py             # CSV download + parse (no browser, no LLM)
    bidsandtenders.py         # Common handler for ~20 BidsAndTenders subdomains
    browser_scraper.py        # Generic browser-use scraper for other portals
    extraction.py             # LLM extraction: HTML -> structured fields via instructor
    embeddings.py             # OpenAI embedding generation
    validation.py             # Post-extraction validation rules
    audit.py                  # scrape_runs logging
  tests/
    __init__.py
    conftest.py               # Shared fixtures
    test_models.py            # Pydantic model validation tests
    test_canadabuys.py        # CanadaBuys CSV parsing tests
    test_extraction.py        # LLM extraction tests (mocked)
    test_validation.py        # Post-extraction validation tests
    test_upsert.py            # Database upsert tests
    test_embeddings.py        # Embedding generation tests (mocked)
```

### Pattern 1: Three-Path Ingestion
**What:** Different portal types use different ingestion pipelines converging at the same database upsert point.
**When to use:** Always -- this is the core architecture.

```python
# orchestrator.py
async def scrape_portal(portal: Portal, db: Connection) -> ScrapeResult:
    """Route portal to the right handler based on its type."""
    run = await start_scrape_run(db, portal.id)
    try:
        if portal.name == "CanadaBuys":
            listings = await canadabuys_ingest(portal)
        elif "bidsandtenders" in portal.url:
            listings = await bidsandtenders_scrape(portal)
        else:
            listings = await browser_scrape(portal)

        # All paths converge here
        validated = [validate_listing(l) for l in listings]
        embedded = await generate_embeddings(validated)
        stats = await upsert_listings(db, portal.id, embedded)
        await complete_scrape_run(db, run.id, stats)
        return stats
    except Exception as e:
        await fail_scrape_run(db, run.id, str(e))
        raise
```

### Pattern 2: Browser Use for Navigation, Playwright for Extraction
**What:** Use browser-use Agent to navigate to listing pages and handle pagination, then drop down to Playwright's `page.content()` to grab raw HTML for LLM extraction.
**When to use:** For all browser-scraped portals.

```python
from browser_use import Agent, Browser
from pydantic import BaseModel
from instructor import from_openai
from openai import OpenAI

class ProcurementListing(BaseModel):
    title: str
    description: str | None = None
    closing_date: str | None = None  # ISO format or None
    posting_date: str | None = None
    reference_number: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    source_listing_id: str  # Unique ID from source
    source_url: str

async def browser_scrape(portal: Portal) -> list[ProcurementListing]:
    browser = Browser(headless=True)

    # Step 1: Use browser-use to navigate to listing page
    agent = Agent(
        task=f"Go to {portal.url} and find the page listing open procurement opportunities. "
             f"Navigate to the main tender/bid listing page. Do not click on individual listings.",
        llm=ChatOpenAI(model="gpt-4o-mini"),
        browser=browser,
        max_actions_per_step=4,
        max_failures=3,
    )
    history = await agent.run(max_steps=10)

    # Step 2: Get raw HTML via Playwright
    page = browser.current_page  # Access underlying Playwright page
    html_content = await page.content()

    # Step 3: Extract listings from HTML using instructor + GPT-4o-mini
    listings = await extract_listings_from_html(html_content, portal)

    await browser.close()
    return listings
```

### Pattern 3: CanadaBuys CSV Direct Ingestion
**What:** Download CSV, parse with Python csv module, map fields directly. Zero LLM cost.
**When to use:** CanadaBuys federal portal only.

```python
import httpx
import csv
import io

CANADABUYS_OPEN_URL = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"

async def canadabuys_ingest(portal: Portal) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(CANADABUYS_OPEN_URL, timeout=120)
        resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    listings = []
    for row in reader:
        listing = {
            "title": row.get("title-titre-eng") or row.get("title-titre-fra"),
            "description": row.get("tenderDescription-descriptionAppelOffres-eng")
                          or row.get("tenderDescription-descriptionAppelOffres-fra"),
            "source_listing_id": row["referenceNumber-numeroReference"],
            "posting_date": row.get("publicationDate-datePublication"),
            "closing_date": row.get("tenderClosingDate-appelOffresDateCloture"),
            "status": map_status(row.get("tenderStatus-appelOffresStatut-eng", "Open")),
            "classification_codes": build_classification_codes(row),
            "contact_info": build_contact_info(row),
            "source_url": row.get("noticeURL-URLavis-eng") or row.get("noticeURL-URLavis-fra"),
            "province": row.get("regionsOfOpportunity-regionAppelOffres-eng"),
            "raw_location": row.get("regionsOfDelivery-regionsLivraison-eng"),
        }
        listings.append(listing)
    return listings
```

### Pattern 4: Upsert with ON CONFLICT
**What:** Insert or update listings based on (source_portal, source_listing_id) composite unique key.
**When to use:** Every listing write.

```python
from psycopg2.extras import execute_values

UPSERT_SQL = """
    INSERT INTO listings (
        source_portal, source_listing_id, title, description, status,
        language, posting_date, closing_date, province, raw_location,
        classification_codes, value_min, value_max, contact_info,
        documents, source_url, embedding, embedding_model, last_scraped_at
    ) VALUES %s
    ON CONFLICT (source_portal, source_listing_id) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        status = EXCLUDED.status,
        closing_date = EXCLUDED.closing_date,
        classification_codes = EXCLUDED.classification_codes,
        value_min = EXCLUDED.value_min,
        value_max = EXCLUDED.value_max,
        contact_info = EXCLUDED.contact_info,
        documents = EXCLUDED.documents,
        source_url = EXCLUDED.source_url,
        embedding = EXCLUDED.embedding,
        embedding_model = EXCLUDED.embedding_model,
        last_scraped_at = NOW(),
        updated_at = NOW(),
        revision = listings.revision + 1
"""

def upsert_listings(conn, portal_id, listings):
    values = [(portal_id, l.source_listing_id, l.title, ...) for l in listings]
    with conn.cursor() as cur:
        execute_values(cur, UPSERT_SQL, values, page_size=100)
    conn.commit()
```

### Pattern 5: Auto-Disable After 5 Consecutive Failures
**What:** Track consecutive failures per portal and auto-disable.
**When to use:** After every failed scrape run.

```python
async def check_auto_disable(db, portal_id: str) -> bool:
    """Disable portal if last 5 runs all failed."""
    query = """
        SELECT status FROM scrape_runs
        WHERE portal_id = %s
        ORDER BY started_at DESC
        LIMIT 5
    """
    rows = await db.fetch(query, portal_id)
    if len(rows) >= 5 and all(r['status'] == 'failed' for r in rows):
        await db.execute(
            "UPDATE portals SET enabled = false, updated_at = NOW() WHERE id = %s",
            portal_id
        )
        logger.warning(f"Auto-disabled portal {portal_id} after 5 consecutive failures")
        return True
    return False
```

### Anti-Patterns to Avoid
- **Using headless=True:** POC confirmed that headless Chromium gets 403-blocked by procurement portals (including CanadaBuys). MUST use headless=False with Xvfb in Docker. The Dockerfile needs `apt-get install -y xvfb` and the entrypoint must use `xvfb-run`.
- **AI for everything:** Do NOT use browser-use or LLM extraction for CanadaBuys. The CSV is structured data -- parsing it with an LLM wastes money and adds latency.
- **Per-portal Playwright selectors:** Do NOT write CSS selectors for each portal. That is the whole point of using browser-use + LLM extraction -- it handles layout diversity.
- **Guessing structured fields:** Do NOT instruct the LLM to "try to determine" NAICS codes or dollar values. The extraction prompt must say "extract only if explicitly stated, otherwise return null."
- **Running all 63 portals in parallel:** Memory and rate limits will cause failures. Run sequentially or in small batches (3-5 concurrent).
- **Embedding before validation:** Generate embeddings AFTER validation passes. Do not waste embedding tokens on invalid listings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output | Custom JSON parsing/regex | instructor + Pydantic | Handles retries, validation, edge cases automatically |
| Browser automation | Per-portal Playwright scripts | browser-use Agent | 63 different layouts is unmaintainable with custom selectors |
| Retry with backoff | Custom retry loops | tenacity library | Battle-tested exponential backoff with jitter |
| robots.txt parsing | Custom parser | robotexclusionrulesparser or urllib.robotparser | Edge cases in robots.txt format are numerous |
| CSV parsing | Regex or split() | Python csv.DictReader | Handles quoting, escaping, multi-line values correctly |
| Token counting | Approximation by character count | tiktoken with cl100k_base | Exact token count prevents API errors |

**Key insight:** The main complexity in this phase is dealing with 63 diverse portal layouts. Browser Use + LLM extraction exists precisely to avoid writing 63 custom scrapers. The pipeline architecture should maximize code reuse across the three ingestion paths while keeping per-portal error isolation clean.

## Common Pitfalls

### Pitfall 1: LLM Hallucinating Structured Fields
**What goes wrong:** The LLM invents NAICS codes, dollar values, or closing dates that look plausible but are wrong.
**Why it happens:** LLMs are completion machines; they fill gaps by default.
**How to avoid:** Extraction prompt must explicitly say: "Return null for any field not clearly stated in the text. Never infer or estimate values." Use Pydantic `Optional[T] = None` for all non-required fields. Validate that classification codes match known NAICS/UNSPSC patterns before accepting.
**Warning signs:** Listings with suspiciously complete metadata from portals known to have sparse data.

### Pitfall 2: Browser Use Over-Navigation
**What goes wrong:** The AI agent clicks through too many pages, opens PDFs, fills in search forms, or gets stuck in loops.
**Why it happens:** The task prompt is too vague, or the agent encounters unexpected UI patterns.
**How to avoid:** Keep navigation tasks narrow: "Go to [URL], find the tender listing table, stop." Set `max_steps=10` and `step_timeout=120`. Use `allowed_domains` to prevent navigation away from the target portal. Define clear success criteria.
**Warning signs:** Agent using 20+ steps per portal, high LLM token usage for navigation.

### Pitfall 3: Token Explosion on Large HTML Pages
**What goes wrong:** Passing full HTML (50-100KB) to the LLM for extraction exceeds context limits and costs too much.
**Why it happens:** Government portal pages have massive HTML with navigation, footers, scripts, and CSS.
**How to avoid:** Strip HTML to meaningful text content using BeautifulSoup before sending to LLM. Remove `<script>`, `<style>`, `<nav>`, `<footer>` tags. Target the main content area. A 50KB HTML page might reduce to 5KB of useful text.
**Warning signs:** Extraction calls using >10K tokens per listing, high monthly OpenAI bills.

### Pitfall 4: BidsAndTenders AJAX-Loaded Content
**What goes wrong:** The tender listing table on BidsAndTenders subdomains is empty when you read `page.content()` because data loads via AJAX after initial page render.
**Why it happens:** The platform uses jQuery AJAX to populate the tender table dynamically.
**How to avoid:** Wait for network idle or specific elements to appear. Browser-use handles this automatically via its `wait_for_network_idle_page_load_time` setting (default 0.5s -- may need to increase to 2-3s for BidsAndTenders). Alternatively, use Playwright's `page.wait_for_selector()` to wait for the tender table to populate.
**Warning signs:** Empty listing arrays from BidsAndTenders portals that clearly have open tenders on their website.

### Pitfall 5: CanadaBuys CSV Encoding Issues
**What goes wrong:** French characters (accents) or long description fields cause parsing errors.
**Why it happens:** The CSV uses UTF-8 with BOM (byte order mark) and has fields with multi-line content and embedded quotes.
**How to avoid:** Use `utf-8-sig` encoding when reading the CSV. Handle multi-line description fields. The CSV has known issues with long descriptions in spreadsheet tools; Python's csv module handles them correctly.
**Warning signs:** UnicodeDecodeError or malformed rows in parsed data.

### Pitfall 6: Rate Limiting Across APIs
**What goes wrong:** OpenAI API returns 429 errors, or portals block the scraper IP.
**Why it happens:** Hitting rate limits on the OpenAI API or scraping too aggressively.
**How to avoid:** Use tenacity with exponential backoff for all API calls. For portal scraping, add 2-5 second delays between portals. For OpenAI embeddings, batch up to 2048 inputs per call but respect the 300K token limit. For GPT-4o-mini extraction calls, OpenAI rate limits are generous (500K TPM for Tier 1).
**Warning signs:** Intermittent 429 errors, portals returning 403 or CAPTCHA pages.

## Code Examples

### Structured Extraction with Instructor + GPT-4o-mini
```python
# Source: instructor docs (https://python.useinstructor.com/)
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class ProcurementListing(BaseModel):
    """A single procurement listing extracted from a portal page."""
    title: str = Field(description="The title of the procurement opportunity")
    description: Optional[str] = Field(None, description="Description text, if present")
    reference_number: Optional[str] = Field(None, description="Official reference/solicitation number")
    posting_date: Optional[str] = Field(None, description="Date posted, ISO format YYYY-MM-DD")
    closing_date: Optional[str] = Field(None, description="Submission deadline, ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    status: Optional[str] = Field(None, description="Open, Closed, Awarded, Cancelled")
    value_min: Optional[float] = Field(None, description="Minimum contract value if explicitly stated")
    value_max: Optional[float] = Field(None, description="Maximum contract value if explicitly stated")
    contact_name: Optional[str] = Field(None, description="Contact person name")
    contact_email: Optional[str] = Field(None, description="Contact email address")
    source_url: Optional[str] = Field(None, description="Direct URL to this listing")

class ExtractionResult(BaseModel):
    """All listings found on the page."""
    listings: list[ProcurementListing]

client = instructor.from_openai(OpenAI())

def extract_listings(html_text: str, portal_name: str) -> ExtractionResult:
    return client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=ExtractionResult,
        max_retries=2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a procurement data extraction assistant. "
                    "Extract all procurement listings visible on this page. "
                    "CRITICAL RULES:\n"
                    "- Only extract fields that are EXPLICITLY stated in the text.\n"
                    "- Return null for any field you cannot find verbatim.\n"
                    "- NEVER guess or infer NAICS/UNSPSC codes, dollar values, or dates.\n"
                    "- Dates must be in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).\n"
                    "- If a value range is stated, extract both min and max.\n"
                    "- Include the source URL for each listing if visible as a link.\n"
                ),
            },
            {
                "role": "user",
                "content": f"Extract all procurement listings from this {portal_name} page:\n\n{html_text}",
            },
        ],
    )
```

### OpenAI Embeddings - Batch Processing
```python
# Source: OpenAI docs (https://developers.openai.com/api/docs/guides/embeddings/)
from openai import OpenAI
import tiktoken

client = OpenAI()
encoding = tiktoken.get_encoding("cl100k_base")

def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    text-embedding-3-small: 1536 dimensions, 8192 max input tokens per text.
    Max 300,000 tokens summed across all inputs in one request.
    Cost: $0.02/1M tokens (standard), $0.01/1M tokens (batch API).
    """
    # Prepare text: combine title + description, truncate if needed
    prepared = []
    for text in texts:
        tokens = encoding.encode(text)
        if len(tokens) > 8000:  # Leave margin below 8192 limit
            text = encoding.decode(tokens[:8000])
        prepared.append(text)

    # Batch in chunks to stay under 300K token limit
    all_embeddings = []
    batch_tokens = 0
    batch = []

    for text in prepared:
        text_tokens = len(encoding.encode(text))
        if batch_tokens + text_tokens > 250_000 or len(batch) >= 2048:
            # Flush current batch
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            all_embeddings.extend([e.embedding for e in response.data])
            batch = []
            batch_tokens = 0
        batch.append(text)
        batch_tokens += text_tokens

    # Flush remaining
    if batch:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        all_embeddings.extend([e.embedding for e in response.data])

    return all_embeddings
```

### CanadaBuys CSV Field Mapping
```python
# Source: CanadaBuys open data (https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2)
# CSV columns (bilingual, format: english-french):

CANADABUYS_FIELD_MAP = {
    # Core fields
    "title": "title-titre-eng",
    "title_fr": "title-titre-fra",
    "description": "tenderDescription-descriptionAppelOffres-eng",
    "description_fr": "tenderDescription-descriptionAppelOffres-fra",
    "reference_number": "referenceNumber-numeroReference",
    "solicitation_number": "solicitationNumber-numeroSollicitation",
    "amendment_number": "amendmentNumber-numeroModification",

    # Dates
    "posting_date": "publicationDate-datePublication",
    "closing_date": "tenderClosingDate-appelOffresDateCloture",
    "amendment_date": "amendmentDate-dateModification",
    "contract_start_date": "expectedContractStartDate-dateDebutContratPrevue",
    "contract_end_date": "expectedContractEndDate-dateFinContratPrevue",

    # Status and classification
    "status": "tenderStatus-appelOffresStatut-eng",
    "gsin": "gsin-nibs",
    "gsin_desc": "gsinDescription-nibsDescription-eng",
    "unspsc": "unspsc",
    "unspsc_desc": "unspscDescription-eng",
    "procurement_category": "procurementCategory-categorieApprovisionnement",
    "notice_type": "noticeType-avisType-eng",
    "procurement_method": "procurementMethod-methodeApprovisionnement-eng",

    # Geography
    "regions_of_opportunity": "regionsOfOpportunity-regionAppelOffres-eng",
    "regions_of_delivery": "regionsOfDelivery-regionsLivraison-eng",

    # Contact
    "contact_name": "contactInfoName-informationsContactNom",
    "contact_email": "contactInfoEmail-informationsContactCourriel",
    "contact_phone": "contactInfoPhone-contactInfoTelephone",

    # Contracting entity
    "entity_name": "contractingEntityName-nomEntitContractante-eng",
    "entity_city": "contractingEntityAddressCity-entiteContractanteAdresseVille-eng",
    "entity_province": "contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng",

    # URLs
    "notice_url": "noticeURL-URLavis-eng",
    "notice_url_fr": "noticeURL-URLavis-fra",
}

# Procurement category codes
PROCUREMENT_CATEGORIES = {
    "CNST": "Construction",
    "GD": "Goods",
    "SRV": "Services",
    "SRVTGD": "Services related to goods",
}
```

### Browser Use Configuration for Scraping
```python
# Source: browser-use docs (https://docs.browser-use.com)
from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI

# Browser configuration for scraping
browser = Browser(
    headless=True,                              # No GUI needed in pipeline
    allowed_domains=["*.bidsandtenders.ca"],     # Restrict navigation scope
    minimum_wait_page_load_time=1.0,            # Wait for initial render
    wait_for_network_idle_page_load_time=2.0,   # Wait for AJAX content
    wait_between_actions=1.0,                    # Be respectful to servers
    keep_alive=True,                            # Reuse browser across portals
)

# Agent configuration for navigation
agent = Agent(
    task="Navigate to the open tenders listing page",
    llm=ChatOpenAI(model="gpt-4o-mini"),
    browser=browser,
    max_actions_per_step=4,          # Limit actions per LLM call
    max_failures=3,                  # Retry threshold
    llm_timeout=90,                  # 90s per LLM call
    step_timeout=120,                # 120s per step
    use_vision=False,                # DOM-only mode saves tokens
)
```

### Post-Extraction Validation
```python
from datetime import datetime
from pydantic import BaseModel, validator, Field
from typing import Optional

class ValidatedListing(BaseModel):
    title: str
    description: Optional[str] = None
    posting_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None

    @validator("closing_date")
    def closing_after_posting(cls, v, values):
        """SCRP-04: Reject if closing_date < posting_date."""
        if v and values.get("posting_date") and v < values["posting_date"]:
            return None  # Null out invalid date rather than reject listing
        return v

    @validator("value_min", "value_max")
    def plausible_value(cls, v):
        """SCRP-04: Reject implausible contract values."""
        if v is not None and (v < 0 or v > 10_000_000_000):  # $10B cap
            return None  # Null out rather than reject listing
        return v

    @validator("value_max")
    def max_gte_min(cls, v, values):
        if v is not None and values.get("value_min") is not None:
            if v < values["value_min"]:
                return None
        return v

def compute_completeness_score(listing: dict) -> float:
    """Score 0.0-1.0 based on how many fields are populated."""
    scored_fields = [
        "title", "description", "posting_date", "closing_date",
        "classification_codes", "value_min", "contact_info",
        "province", "source_url"
    ]
    filled = sum(1 for f in scored_fields if listing.get(f) is not None)
    return round(filled / len(scored_fields), 2)
```

## CanadaBuys Data Details

### CSV Files Available
| File | URL | Update Frequency | Use Case |
|------|-----|-----------------|----------|
| Open tender notices | `canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv` | Daily, 7-8:30 AM ET | Primary: all currently open tenders |
| New tender notices | `canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv` | Every 2 hours (6:15 AM - 10:15 PM) | Incremental: recently added notices |
| FY 2025-2026 | `canadabuys.canada.ca/opendata/pub/2025-2026-TenderNotice-AvisAppelOffres.csv` | Daily | Historical: all notices this fiscal year |
| Complete dataset | `canadabuys.canada.ca/opendata/pub/tenderNoticeComplete-avisAppelOffresComplet.csv` | Daily | Full history from 2022-08-08 |

**Recommended approach:** Download the "open tender notices" file daily for the nightly run. This gives all currently open tenders. For initial backfill, download the complete dataset once. The "new tender notices" file is useful for more frequent intraday updates (future optimization).

### Key Data Quality Notes
- All fields are bilingual (English and French variants)
- Fields are prefixed with English name, suffixed with French name, separated by hyphen
- The CSV uses UTF-8 with BOM encoding
- Long description fields may contain newlines and quotes (handled by csv.DictReader)
- GSIN and UNSPSC codes are provided with descriptions
- Some fields use asterisk prefix (e.g., `*SRV`) indicating the value comes from a standard code table
- SAP Ariba-sourced tenders appear the day after publication due to nightly sync

## BidsAndTenders Platform Analysis

### Platform Characteristics
- ~20 of our 63 portals are BidsAndTenders subdomains (e.g., mississauga.bidsandtenders.ca, hamilton.bidsandtenders.ca)
- All subdomains share identical HTML/JS structure
- Tender listings loaded dynamically via jQuery AJAX -- NOT in initial HTML
- Uses module-based routing: `/Module/Tenders/en` is the listing page
- Pagination: 15/25/50/100 items per page with Previous/Next navigation
- Status filters: Open, Closed, Awarded, Cancelled, etc.
- No public API documented; the platform actively restricts scraping bots
- Tender detail pages use UUID-based URLs: `/Module/Tenders/en/Tender/Detail/{uuid}`

### Recommended Scraping Approach
Write a single `bidsandtenders.py` handler that works for all ~20 subdomains. The approach:
1. Navigate to `{subdomain}.bidsandtenders.ca/Module/Tenders/en` with browser-use
2. Wait for AJAX-loaded content (increase `wait_for_network_idle_page_load_time` to 3s)
3. Extract the listing table HTML via `page.content()`
4. Parse listing links from the table
5. For each listing, navigate to the detail page and extract content
6. Use the same LLM extraction pipeline as other portals

Since all subdomains share structure, the single handler with the subdomain as a parameter eliminates ~20 duplicate scrapers.

## Cost Estimation

### Per-Night Cost Model (all 63 portals)

| Component | Volume | Unit Cost | Nightly Cost |
|-----------|--------|-----------|-------------|
| **CanadaBuys** (CSV download) | 1 HTTP request | Free | $0.00 |
| **Browser-Use navigation** (GPT-4o-mini) | ~42 portals x ~5 steps x ~1K tokens | $0.15/1M input | ~$0.05 |
| **HTML extraction** (GPT-4o-mini) | ~3,000 listings x ~3K tokens input | $0.15/1M input + $0.60/1M output | ~$2.50 |
| **Embeddings** (text-embedding-3-small) | ~3,000 listings x ~500 tokens | $0.02/1M tokens | ~$0.03 |
| **Total estimate** | | | **~$2.60/night** |

**Conservative estimate with safety margin:** $5-10/night

**Cost-saving strategies:**
- CanadaBuys via CSV: $0 (vs ~$1.50 if scraped with LLM)
- BidsAndTenders common handler: reduces navigation steps
- Strip HTML before extraction: reduces token count by 5-10x
- Use `use_vision=False` on browser-use: DOM-only mode is cheaper

### LLM Token Estimates
- Average government portal page HTML: 30-80KB raw, 3-8KB after HTML stripping
- Average extraction per listing: ~3,000 input tokens, ~500 output tokens
- Average navigation step: ~1,000 input tokens, ~200 output tokens
- Average embedding text (title + description): ~500 tokens

## robots.txt Compliance Strategy

**Approach:** Before scraping any portal, fetch and respect its robots.txt file.

```python
from urllib.robotparser import RobotFileParser

def check_robots_txt(portal_url: str, user_agent: str = "ProcurementBot/1.0") -> bool:
    """Check if scraping is allowed by robots.txt."""
    rp = RobotFileParser()
    rp.set_url(f"{portal_url.rstrip('/')}/robots.txt")
    try:
        rp.read()
        return rp.can_fetch(user_agent, portal_url)
    except Exception:
        # If robots.txt cannot be fetched, proceed with caution
        return True  # Most government portals don't have robots.txt
```

**Notes:**
- Most government portals do not have restrictive robots.txt
- BidsAndTenders actively restricts bots -- the scraper should use a reasonable User-Agent and respectful request rates
- This is a compliance check, not a legal opinion; government procurement data is generally considered public information
- Log robots.txt status per portal for the audit trail

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-site CSS selectors (Scrapy/BeautifulSoup) | AI-driven navigation (browser-use) | 2025 | Eliminates per-site scraper maintenance |
| Regex/template extraction | LLM structured extraction (instructor/LangExtract) | 2025 | Handles diverse layouts without custom parsers |
| text-embedding-ada-002 | text-embedding-3-small | Jan 2024 | 5x cheaper, better performance, same 1536 dims |
| GPT-4 for extraction | GPT-4o-mini | Jul 2024 | 100x cheaper, adequate for structured extraction |
| Elasticsearch for search | pgvector | 2023-2024 | One fewer service, good enough for <100K documents |

**Deprecated/outdated:**
- text-embedding-ada-002: replaced by text-embedding-3-small (better + cheaper)
- Browser Use v1.0: v2.0 released Jan 2026 with +12% accuracy improvement
- LangExtract uses dataclass-based examples, not Pydantic models directly (a common misconception)

## Open Questions

1. **BidsAndTenders bot detection**
   - What we know: The platform actively restricts scrapers and bots; it modernized infrastructure to counter data scrapers
   - What is unclear: Specific detection mechanisms (IP blocking, CAPTCHA, rate limits). Whether using browser-use with a real browser profile avoids detection
   - Recommendation: Start with 2-3 BidsAndTenders portals and monitor for blocks. Add delays (3-5s between requests). Use browser-use's stealth features if needed. Have a fallback plan to reduce scraping frequency on resistant portals

2. **Browser Use resource consumption**
   - What we know: Each browser-use Agent spawns a Playwright/Chromium instance. Docker container has 4GB memory limit and 2GB shm_size
   - What is unclear: Exact memory per browser instance when running 63 portals sequentially. Whether browser instances properly release memory
   - Recommendation: Run portals sequentially (not parallel) initially. Monitor memory usage. Add `browser.close()` between portals. Consider restarting browser every 10-20 portals

3. **SEAO (Quebec) open data feed**
   - What we know: CONTEXT.md mentions investigating SEAO. SEAO portals require login and are marked `enabled=false`
   - What is unclear: Whether SEAO has a public API or data feed
   - Recommendation: Defer investigation to after core pipeline works. SEAO portals are all `requires_login=true` and `enabled=false`, so they are naturally excluded from Phase 2 first pass

4. **Cost at scale validation**
   - What we know: Estimates above are theoretical. Actual costs depend on portal HTML complexity, navigation steps needed, and failure/retry rates
   - What is unclear: Real-world cost per portal
   - Recommendation: Run benchmark on 5 representative portals (1 CanadaBuys, 2 BidsAndTenders, 2 diverse) and measure actual token usage before enabling all 63

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (standard Python) |
| Config file | None -- Wave 0 gap, need pytest.ini or pyproject.toml |
| Quick run command | `pytest scraper/tests/ -x -q` |
| Full suite command | `pytest scraper/tests/ -v` |
| Estimated runtime | ~5-10 seconds (with mocked API calls) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCRP-01 | Pipeline runs against all enabled portals | integration | `pytest scraper/tests/test_orchestrator.py -x` | No -- Wave 0 gap |
| SCRP-02 | Structured extraction produces valid fields | unit | `pytest scraper/tests/test_extraction.py -x` | No -- Wave 0 gap |
| SCRP-03 | Scrape runs logged to audit table | unit | `pytest scraper/tests/test_audit.py -x` | No -- Wave 0 gap |
| SCRP-04 | Post-extraction validation rejects invalid data | unit | `pytest scraper/tests/test_validation.py -x` | No -- Wave 0 gap |
| SCRP-05 | Embeddings generated for each listing | unit | `pytest scraper/tests/test_embeddings.py -x` | No -- Wave 0 gap |
| SCRP-06 | Upsert on composite key handles updates | unit | `pytest scraper/tests/test_upsert.py -x` | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task, run: `pytest scraper/tests/ -x -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work`
- **Estimated feedback latency per task:** ~5-10 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `scraper/tests/__init__.py` -- package init
- [ ] `scraper/tests/conftest.py` -- shared fixtures (mock OpenAI, mock DB, sample HTML)
- [ ] `scraper/tests/test_models.py` -- Pydantic model validation
- [ ] `scraper/tests/test_canadabuys.py` -- CSV parsing with sample data
- [ ] `scraper/tests/test_extraction.py` -- LLM extraction with mocked responses
- [ ] `scraper/tests/test_validation.py` -- post-extraction validation rules
- [ ] `scraper/tests/test_upsert.py` -- DB upsert logic
- [ ] `scraper/tests/test_embeddings.py` -- embedding generation with mocked API
- [ ] `scraper/tests/test_audit.py` -- scrape run logging
- [ ] `pytest.ini` or section in `pyproject.toml` -- pytest configuration
- [ ] Framework install: `pip install pytest pytest-asyncio` -- add to requirements.txt

## Sources

### Primary (HIGH confidence)
- [CanadaBuys Open Data Portal](https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2) -- CSV file URLs, update frequency, dataset structure
- CanadaBuys CSV header (directly fetched) -- complete field list verified from actual CSV download
- [OpenAI Embeddings Guide](https://developers.openai.com/api/docs/guides/embeddings/) -- text-embedding-3-small specs, batch limits, pricing
- [OpenAI Pricing](https://platform.openai.com/docs/pricing) -- GPT-4o-mini and embedding costs
- [Browser Use Docs](https://docs.browser-use.com) -- Agent parameters, Browser config, output format, parallel agents
- [Browser Use GitHub](https://github.com/browser-use/browser-use) -- v0.11.x, installation, quickstart
- [Instructor Library](https://python.useinstructor.com/) -- structured extraction with Pydantic
- [LangExtract PyPI](https://pypi.org/project/langextract/) -- v1.1.1, Python 3.10+, Apache 2.0

### Secondary (MEDIUM confidence)
- [LangExtract + OpenAI Guide (Telerik)](https://www.telerik.com/blogs/step-by-step-guide-using-langextract-openai) -- code examples for OpenAI integration
- [BidsAndTenders Platform](https://bids.bidsandtenders.ca/Module/Tenders/en) -- HTML structure analysis
- [Mississauga BidsAndTenders](https://mississauga.bidsandtenders.ca/Module/Tenders/en) -- AJAX loading pattern confirmed

### Tertiary (LOW confidence)
- BidsAndTenders bot detection claims -- based on marketing materials, not verified technically
- SEAO open data feed existence -- mentioned in CONTEXT.md but not verified
- Exact memory usage per browser-use instance -- needs runtime benchmarking

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified on PyPI/GitHub with current versions
- Architecture: MEDIUM-HIGH -- patterns are well-established but browser-use for scraping is relatively new (2025)
- CanadaBuys: HIGH -- CSV structure directly verified by downloading actual data
- BidsAndTenders: MEDIUM -- AJAX structure confirmed but bot detection risk is uncertain
- Cost estimates: MEDIUM -- based on published pricing but actual usage depends on portal complexity
- Pitfalls: HIGH -- well-documented issues in the scraping and LLM extraction domain

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days -- OpenAI pricing and browser-use versions may change)
