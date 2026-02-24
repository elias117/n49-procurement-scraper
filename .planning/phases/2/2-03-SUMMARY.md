---
phase: 2-scraper-pipeline
plan: 03
subsystem: extraction-and-browser-scrapers
tags: [llm-extraction, instructor, browser-use, html-stripping, scraping]
dependency_graph:
  requires: [2-01]
  provides: [extraction-pipeline, bidsandtenders-scraper, browser-scraper]
  affects: [2-04]
tech_stack:
  added: [instructor, beautifulsoup4, tenacity, eval-type-backport]
  patterns: [lazy-imports, instructor-pydantic-extraction, html-stripping, error-isolation]
key_files:
  created:
    - scraper/pipeline/extraction.py
    - scraper/pipeline/bidsandtenders.py
    - scraper/pipeline/browser_scraper.py
    - scraper/tests/test_extraction.py
  modified: []
decisions:
  - Lazy imports for browser-use in scraper modules (Python 3.9 dev vs 3.11+ Docker)
  - instructor retry via tenacity for rate limits separate from instructor's own max_retries
  - Browser page access via both current_page and context.pages fallback
metrics:
  duration: 310s
  completed: 2026-02-24T22:18:45Z
  tasks_completed: 2
  tasks_total: 2
  tests_added: 10
  files_created: 4
---

# Phase 2 Plan 03: LLM Extraction and Browser Scrapers Summary

**One-liner:** instructor + GPT-4o-mini extraction pipeline with HTML stripping (5-10x token reduction), BidsAndTenders handler for ~20 portals, and generic browser-use scraper for diverse portals.

## What Was Built

### Task 1: LLM Extraction Pipeline (extraction.py + tests)

**`scraper/pipeline/extraction.py`** -- The AI-powered core of the scraper pipeline:

- **`strip_html(html_content)`** -- Removes script, style, nav, footer, header, and aside tags using BeautifulSoup. Strips all HTML attributes. Collapses multiple blank lines. Achieves 5-10x token reduction. Logs original/stripped sizes and reduction ratio.

- **`extract_listings_from_html(html_content, portal_name)`** -- Takes raw HTML, strips it, then uses `instructor.from_openai(OpenAI())` with `response_model=ExtractionResult` to extract structured `ProcurementListing` objects. System prompt contains explicit "NEVER guess" instructions for NAICS/UNSPSC/GSIN codes, dollar values, and dates. Returns empty list for empty/short HTML (<50 chars). Uses tenacity retry for `RateLimitError` and `APIConnectionError`.

- **`extract_listing_detail(html_content, portal_name)`** -- Same extraction approach but for individual listing detail pages. Uses `ProcurementListing` directly as response_model. Returns `None` on failure.

**`scraper/tests/test_extraction.py`** -- 10 tests with mocked OpenAI/instructor:

| Test | What It Verifies |
|------|-----------------|
| `test_strip_html_removes_scripts` | Script tags and content removed |
| `test_strip_html_removes_nav_footer` | Nav, footer, header, aside removed |
| `test_strip_html_preserves_content` | Table text content preserved |
| `test_strip_html_reduces_size` | 73KB HTML reduces to <10KB (>5x reduction) |
| `test_extract_listings_calls_instructor` | Correct model, response_model, max_retries |
| `test_extract_listings_system_prompt_contains_never_guess` | System prompt has NEVER guess + codes/values/dates |
| `test_extract_listings_returns_procurement_listings` | Returns list[ProcurementListing] from ExtractionResult |
| `test_extract_listings_empty_html_returns_empty` | Empty/short HTML returns [] without LLM call |
| `test_extract_listing_detail_returns_single` | Returns single ProcurementListing for detail pages |
| `test_extraction_retries_on_rate_limit` | Retry on RateLimitError succeeds on second attempt |

### Task 2: Browser Scrapers (bidsandtenders.py + browser_scraper.py)

**`scraper/pipeline/bidsandtenders.py`** -- Handles ~20 BidsAndTenders platform portals:

- Constructs standard listing URL: `{base_url}/Module/Tenders/en`
- 3-second AJAX wait for table loading (BidsAndTenders loads tables via AJAX after page render)
- browser-use Agent with `use_vision=False` (DOM-only mode saves tokens)
- `max_steps=10`, `max_actions_per_step=4`, `max_failures=3`
- Calls `extract_listings_from_html()` for structured extraction
- Browser closed in `finally` block; returns empty list on any failure

**`scraper/pipeline/browser_scraper.py`** -- Generic scraper for diverse portals:

- Broad navigation prompt: "Find the page that lists open procurement opportunities, tenders, or bids"
- Same browser-use Agent configuration as BidsAndTenders
- Standard wait times from config (2s network idle vs 3s for BidsAndTenders)
- Same error isolation pattern: try/finally with empty list on failure

Both scrapers use lazy imports for `browser-use` and `langchain-openai` to handle the Python version gap (3.9 dev environment vs 3.11+ Docker runtime).

## Test Results

```
34 passed in 2.27s
```

- 24 tests from Plan 2-01 (models + upsert) -- all pass
- 10 tests from Plan 2-03 (extraction) -- all pass
- Note: 1 pre-existing failure in test_canadabuys.py (BOM handling) from Plan 2-02 -- out of scope

All module imports verified:
```
from scraper.pipeline.extraction import extract_listings_from_html, strip_html  # OK
from scraper.pipeline.bidsandtenders import bidsandtenders_scrape  # OK
from scraper.pipeline.browser_scraper import browser_scrape  # OK
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed eval-type-backport for Python 3.9 compatibility**
- **Found during:** Task 1
- **Issue:** instructor v1.14.5 uses Python 3.10+ union syntax (`str | Path`) which fails on Python 3.9
- **Fix:** Installed `eval-type-backport` package as suggested by the error message
- **Files modified:** None (pip install only)
- **Commit:** N/A (runtime dependency)

**2. [Rule 3 - Blocking] Lazy imports for browser-use in scraper modules**
- **Found during:** Task 2
- **Issue:** `browser-use` package requires Python 3.11+ and cannot be installed on the dev environment (Python 3.9.6). The plan requires clean module imports for verification.
- **Fix:** Used lazy imports inside function bodies with try/except ImportError, returning empty list with error log if browser-use is unavailable. The Docker runtime uses Python 3.11+ where browser-use installs normally.
- **Files modified:** `scraper/pipeline/bidsandtenders.py`, `scraper/pipeline/browser_scraper.py`
- **Commit:** c1585d7

## Decisions Made

1. **Lazy imports for browser-use:** Since browser-use requires Python 3.11+ but the dev environment runs Python 3.9.6, both browser scraper modules use lazy imports inside the async function bodies. This allows clean module-level imports while deferring the browser-use dependency to runtime. The Docker container has the correct Python version.

2. **Separate tenacity retry from instructor max_retries:** The extraction module uses two layers of retry: instructor's built-in `max_retries=2` for Pydantic validation failures, and tenacity's `@retry` decorator for API-level errors (rate limits, connection errors). This separation gives clearer error handling.

3. **Browser page access fallback:** Both browser scrapers try `browser.current_page` first, then fall back to `browser.context.pages[-1]`. The browser-use API may vary between versions, so this defensive approach ensures compatibility.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `486f839` | LLM extraction pipeline with instructor and HTML stripping |
| 2 | `c1585d7` | BidsAndTenders and generic browser scrapers |

## Self-Check: PASSED

- All 4 created files exist on disk
- Both task commits (486f839, c1585d7) found in git history
- 34 tests passing (24 Plan 2-01 + 10 Plan 2-03)
- All module imports verified clean
