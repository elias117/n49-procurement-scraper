---
phase: 2-scraper-pipeline
plan: 03
type: execute
wave: 2
depends_on: ["2-01"]
files_modified:
  - scraper/pipeline/extraction.py
  - scraper/pipeline/bidsandtenders.py
  - scraper/pipeline/browser_scraper.py
  - scraper/tests/test_extraction.py
autonomous: true
requirements:
  - SCRP-02

must_haves:
  truths:
    - "LLM extraction produces ProcurementListing objects from raw HTML text"
    - "HTML is stripped of scripts, styles, nav, and footer before LLM extraction (5-10x token reduction)"
    - "Extraction prompt explicitly instructs LLM to never guess structured fields"
    - "BidsAndTenders handler works for any subdomain by parameterizing the URL"
    - "Browser-use navigates to listing pages with max_steps=10 and use_vision=False"
    - "Generic browser scraper handles diverse portal layouts via AI navigation"
  artifacts:
    - path: "scraper/pipeline/extraction.py"
      provides: "LLM extraction: HTML to structured ProcurementListing list"
      exports: ["extract_listings_from_html", "strip_html"]
    - path: "scraper/pipeline/bidsandtenders.py"
      provides: "BidsAndTenders subdomain scraper"
      exports: ["bidsandtenders_scrape"]
    - path: "scraper/pipeline/browser_scraper.py"
      provides: "Generic browser-use scraper for diverse portals"
      exports: ["browser_scrape"]
    - path: "scraper/tests/test_extraction.py"
      provides: "Extraction tests with mocked OpenAI"
  key_links:
    - from: "scraper/pipeline/extraction.py"
      to: "scraper/models.py"
      via: "Uses ProcurementListing and ExtractionResult as instructor response_model"
      pattern: "response_model=ExtractionResult"
    - from: "scraper/pipeline/bidsandtenders.py"
      to: "scraper/pipeline/extraction.py"
      via: "Passes stripped HTML to extract_listings_from_html"
      pattern: "extract_listings_from_html"
    - from: "scraper/pipeline/browser_scraper.py"
      to: "scraper/pipeline/extraction.py"
      via: "Passes stripped HTML to extract_listings_from_html"
      pattern: "extract_listings_from_html"
---

<objective>
Build the LLM extraction pipeline and both browser-based scrapers (BidsAndTenders handler and generic browser scraper).

Purpose: This is the AI-powered core of the scraper (SCRP-02). The extraction module uses instructor + GPT-4o-mini to convert raw HTML into structured ProcurementListing objects. The two browser scrapers use browser-use for navigation and feed HTML to the extraction module. BidsAndTenders handles ~20 portals with one handler; the generic scraper handles the remaining diverse portals.

Output: Three pipeline modules. Both browser scrapers depend on extraction.py. All produce list[ListingRecord] ready for validation and embedding.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/2/2-CONTEXT.md
@.planning/phases/2/2-RESEARCH.md
@.planning/phases/2/2-01-SUMMARY.md
@scraper/models.py
@scraper/config.py
@scraper/tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: LLM extraction with instructor and HTML stripping</name>
  <files>
    scraper/pipeline/extraction.py
    scraper/tests/test_extraction.py
  </files>
  <action>
    **Create `scraper/pipeline/extraction.py`:**

    Use `instructor` library wrapping OpenAI for structured extraction. Per research recommendation: "instructor over LangExtract -- OpenAI-native, Pydantic validation, auto-retry."

    `strip_html(html_content: str) -> str`:
    - Use BeautifulSoup to parse HTML.
    - Remove all `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>` tags and their contents.
    - Remove all HTML attributes (class, id, style, etc.) to reduce token count.
    - Extract text with `get_text(separator='\n', strip=True)`.
    - Collapse multiple blank lines into single newlines.
    - Return cleaned text. This should achieve the 5-10x token reduction mentioned in research.
    - Log: original HTML size, stripped text size, reduction ratio.

    `extract_listings_from_html(html_content: str, portal_name: str) -> list[ProcurementListing]`:
    1. Strip HTML using `strip_html()`.
    2. If stripped text is empty or <50 chars, return empty list with warning log.
    3. Create instructor client: `instructor.from_openai(OpenAI())`.
    4. Call `client.chat.completions.create()` with:
       - `model=config.OPENAI_EXTRACTION_MODEL` (defaults to "gpt-4o-mini")
       - `response_model=ExtractionResult` (from models.py)
       - `max_retries=2` (instructor handles retry with validation feedback)
       - System message (CRITICAL -- this controls extraction quality):
         ```
         You are a procurement data extraction assistant.
         Extract all procurement listings visible on this page.

         CRITICAL RULES:
         - Only extract fields that are EXPLICITLY stated in the text.
         - Return null for any field you cannot find verbatim on the page.
         - NEVER guess or infer NAICS codes, UNSPSC codes, GSIN codes, dollar values, or dates.
         - If a value is ambiguous or unclear, return null.
         - Dates must be in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
         - If a value range is stated (e.g., "$50,000 - $100,000"), extract both min and max.
         - Include the direct URL to each listing if visible as a link.
         - For reference/solicitation numbers, extract exactly as shown.
         - Classification codes: only extract if explicitly labeled as NAICS, UNSPSC, GSIN, or commodity code.
         ```
       - User message: `f"Extract all procurement listings from this {portal_name} page:\n\n{stripped_text}"`
    5. Use tenacity retry for the overall call: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)))`.
    6. Return `result.listings`.
    7. Log: number of listings extracted, portal name.

    `extract_listing_detail(html_content: str, portal_name: str) -> Optional[ProcurementListing]`:
    - Same as above but for a single listing detail page. Uses the same system prompt.
    - response_model is ProcurementListing directly (not ExtractionResult).
    - Returns single ProcurementListing or None on failure.

    **Create `scraper/tests/test_extraction.py`:**

    Mock the OpenAI client and instructor to return predefined extraction results.

    - `test_strip_html_removes_scripts()` — HTML with script tags, verify scripts removed from output.
    - `test_strip_html_removes_nav_footer()` — HTML with nav and footer, verify removed.
    - `test_strip_html_preserves_content()` — HTML with table of listings, verify table text preserved.
    - `test_strip_html_reduces_size()` — 50KB HTML reduces to <10KB text.
    - `test_extract_listings_calls_instructor()` — Verify instructor client is called with correct model and response_model.
    - `test_extract_listings_system_prompt_contains_never_guess()` — Verify "NEVER guess" appears in the system message.
    - `test_extract_listings_returns_procurement_listings()` — Mock returns ExtractionResult with 2 listings, verify list[ProcurementListing] returned.
    - `test_extract_listings_empty_html_returns_empty()` — Empty or very short HTML returns empty list.
    - `test_extract_listing_detail_returns_single()` — Verify single ProcurementListing returned.
    - `test_extraction_retries_on_rate_limit()` — Mock raises RateLimitError first, succeeds second, verify retry.

    Mock strategy: Use `unittest.mock.patch("scraper.pipeline.extraction.instructor")` and `patch("scraper.pipeline.extraction.OpenAI")`. Create a mock that returns an ExtractionResult-like object with `.listings` attribute.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/test_extraction.py -x -q 2>&1</automated>
  </verify>
  <done>
    - strip_html removes script/style/nav/footer tags and achieves 5-10x size reduction
    - extract_listings_from_html uses instructor with GPT-4o-mini and ExtractionResult response_model
    - System prompt includes explicit "NEVER guess" instructions for codes, values, and dates
    - Tenacity retry handles rate limits and connection errors
    - 10 tests pass with mocked OpenAI/instructor
  </done>
</task>

<task type="auto">
  <name>Task 2: BidsAndTenders and generic browser scrapers</name>
  <files>
    scraper/pipeline/bidsandtenders.py
    scraper/pipeline/browser_scraper.py
  </files>
  <action>
    **Create `scraper/pipeline/bidsandtenders.py`:**

    Per research: "~20 portals share identical structure. One handler with subdomain as parameter."

    `async def bidsandtenders_scrape(portal: PortalRecord) -> list[ProcurementListing]`:
    1. Import browser-use: `from browser_use import Agent, Browser` and `from langchain_openai import ChatOpenAI`.
    2. Create Browser instance:
       - `headless=config.BROWSER_HEADLESS`
       - `wait_for_network_idle_page_load_time=3.0` (BidsAndTenders uses AJAX -- needs longer wait per pitfall #4)
       - `wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS`
    3. Construct the tender listing URL: extract subdomain from portal.url, navigate to `{base_url}/Module/Tenders/en` (the standard listing path for all BidsAndTenders subdomains).
    4. Create Agent:
       - task: `f"Navigate to {listing_url}. Wait for the tender listing table to load. The table loads via AJAX after the page renders. Do not click on individual tenders. Do not navigate away from this page."`
       - llm: `ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL)`
       - browser: the browser instance
       - `max_actions_per_step=4`
       - `max_failures=3`
       - `use_vision=False` (DOM-only mode saves tokens per research)
       - `max_steps=config.BROWSER_MAX_STEPS`
    5. Run agent: `history = await agent.run(max_steps=config.BROWSER_MAX_STEPS)`.
    6. Get page HTML: Access the underlying Playwright page via `browser.current_page` or similar browser-use API, call `await page.content()`.
    7. Extract listings: Call `extract_listings_from_html(html_content, portal.name)`.
    8. Close browser: `await browser.close()`.
    9. Set `source_portal = portal.id` on each listing.
    10. Return list of ProcurementListing.
    11. Wrap everything in try/finally to ensure browser.close() is called.
    12. Log: portal name, number of listings found, number of agent steps used.

    **Create `scraper/pipeline/browser_scraper.py`:**

    Generic browser scraper for diverse portals that are not CanadaBuys or BidsAndTenders.

    `async def browser_scrape(portal: PortalRecord) -> list[ProcurementListing]`:
    1. Same browser-use setup as BidsAndTenders but with different task prompt and standard wait times.
    2. Create Browser:
       - `headless=config.BROWSER_HEADLESS`
       - `wait_for_network_idle_page_load_time=config.BROWSER_WAIT_NETWORK_IDLE`
       - `wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS`
    3. Create Agent:
       - task: `f"Navigate to {portal.url}. Find the page that lists open procurement opportunities, tenders, or bids. Look for a listing page with multiple opportunities. Do not click on individual listings. Do not fill in search forms. Stop once you can see a list of opportunities."`
       - llm: `ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL)`
       - browser: the browser instance
       - `max_actions_per_step=4`
       - `max_failures=3`
       - `use_vision=False`
       - `max_steps=config.BROWSER_MAX_STEPS`
    4. Run agent, get HTML, extract listings (same pattern as BidsAndTenders).
    5. Close browser in finally block.
    6. Set `source_portal = portal.id` on each listing.
    7. Return list of ProcurementListing.
    8. Log: portal name, URL, number of listings found.

    **Implementation notes for BOTH scrapers:**
    - Import extraction from: `from scraper.pipeline.extraction import extract_listings_from_html`
    - Both should handle browser-use exceptions gracefully (timeout, navigation failure) by logging the error and returning an empty list rather than crashing the entire pipeline.
    - Use `logging.getLogger(__name__)` for per-module logging.
    - The browser-use API may vary between versions. Consult the installed version's interface. The key operations are: create Browser, create Agent with task, run Agent, get page content from browser, close browser.
    - If `browser.current_page` is not available directly, use the agent's history or browser context to access the Playwright page.

    **No dedicated test file for browser scrapers** -- these modules are integration-heavy (real browser + real LLM). They will be tested via the 5-portal benchmark in Plan 04. The extraction logic they depend on is already tested in test_extraction.py.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -c "from scraper.pipeline.bidsandtenders import bidsandtenders_scrape; from scraper.pipeline.browser_scraper import browser_scrape; print('Browser scrapers import OK')" 2>&1</automated>
    <manual>Review that bidsandtenders.py constructs the /Module/Tenders/en URL correctly and browser_scraper.py has a generic navigation prompt</manual>
  </verify>
  <done>
    - bidsandtenders_scrape handles any BidsAndTenders subdomain with parameterized URL
    - AJAX wait time increased to 3s for BidsAndTenders (per pitfall #4)
    - browser_scrape handles diverse portal layouts with generic AI navigation prompt
    - Both use browser-use Agent with use_vision=False, max_steps=10
    - Both call extract_listings_from_html for structured extraction
    - Both close browser in finally block
    - Both return empty list on failure rather than crashing
  </done>
</task>

</tasks>

<verification>
Run full test suite:
```bash
cd /Users/clawbot/dev
OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/ -x -q
```
All tests pass. All pipeline modules import cleanly.

Verify module imports:
```bash
python -c "
from scraper.pipeline.extraction import extract_listings_from_html, strip_html
from scraper.pipeline.bidsandtenders import bidsandtenders_scrape
from scraper.pipeline.browser_scraper import browser_scrape
print('All extraction and scraper modules OK')
"
```
</verification>

<success_criteria>
1. `from scraper.pipeline.extraction import extract_listings_from_html, strip_html` succeeds
2. `from scraper.pipeline.bidsandtenders import bidsandtenders_scrape` succeeds
3. `from scraper.pipeline.browser_scraper import browser_scrape` succeeds
4. `pytest scraper/tests/test_extraction.py` passes 10+ tests
5. strip_html removes script/style/nav/footer tags
6. System prompt contains "NEVER guess" instructions
7. BidsAndTenders constructs /Module/Tenders/en URL and uses 3s AJAX wait
8. Generic scraper has broad navigation prompt for diverse portals
</success_criteria>

<output>
After completion, create `.planning/phases/2/2-03-SUMMARY.md`
</output>
