"""
Generic browser scraper for diverse procurement portals.

Handles portals that are NOT CanadaBuys or BidsAndTenders. Uses browser-use
Agent with a broad navigation prompt to find and extract procurement listings
from any portal layout.

Uses browser-use Agent for navigation (headless=False to avoid 403 blocks)
and delegates HTML extraction to the extraction module.

When keywords_by_category is provided, the agent searches for keywords using
the portal's search form (if available), with OR-query support and single-keyword
fallback. Action history is inspected to detect whether a search was actually
performed (search_used flag).
"""

from __future__ import annotations

import asyncio
import logging
from typing import NamedTuple
from urllib.parse import urlparse

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.extraction import extract_listing_detail, extract_listings_from_html
from scraper.pipeline.keywords import select_keyword_batch, deduplicate_listings

logger = logging.getLogger(__name__)


class BrowserScrapeResult(NamedTuple):
    """Result from a browser-use scrape with search metadata."""
    listings: list[ProcurementListing]
    search_used: bool  # True if keyword search was performed


def _detect_search_used(history) -> bool:
    """Check if agent action history contains text input (proof of search)."""
    if history is None:
        return False
    try:
        action_names = history.action_names()
        return "input_text" in action_names
    except Exception:
        return False


def _is_sparse(listing: ProcurementListing) -> bool:
    """
    Check if a listing is sparse (missing key detail-page fields).

    A listing is considered sparse if:
    - It has no description at all, OR
    - Its description is very short (<50 chars -- likely a fragment from the
      summary page, not the full detail), OR
    - It has a description but is missing BOTH closing_date and contact
      information (fields typically found on detail pages).

    Listing pages often provide title and closing_date but rarely full
    descriptions, contact info, or dollar values.
    """
    if listing.description is None:
        return True
    if len(listing.description) < 50:
        return True
    if listing.closing_date is None and listing.contact_name is None:
        return True
    return False


def _resolve_url(source_url: str, portal_url: str) -> str:
    """
    Resolve a potentially relative URL against the portal base URL.

    Args:
        source_url: The URL from the listing (may be relative).
        portal_url: The portal's base URL for resolving relative paths.

    Returns:
        An absolute URL string.
    """
    if source_url.startswith(("http://", "https://")):
        return source_url
    from urllib.parse import urljoin
    return urljoin(portal_url, source_url)


def _fix_source_urls(
    listings: list[ProcurementListing],
    page_url: str,
    portal_url: str,
) -> list[ProcurementListing]:
    """
    Replace source_url values that point to external sites.

    The LLM often extracts random URLs from page content (company websites,
    aggregator sites) instead of the actual listing URL on the portal.
    Any source_url whose domain doesn't match the portal domain is replaced
    with the browser's current page URL.
    """
    portal_domain = urlparse(portal_url).netloc.lower()
    for listing in listings:
        if listing.source_url is None:
            listing.source_url = page_url
        else:
            listing_domain = urlparse(listing.source_url).netloc.lower()
            if listing_domain and listing_domain != portal_domain:
                listing.source_url = page_url
    return listings


def _merge_detail(
    original: ProcurementListing, detail: ProcurementListing
) -> ProcurementListing:
    """
    Merge detail page data into an original sparse listing.

    For each field, uses the detail page value if the original is None.
    The original title is always preserved (it came from the listing page).

    Args:
        original: The sparse listing from the listing page.
        detail: The full listing extracted from the detail page.

    Returns:
        A new ProcurementListing with merged fields.
    """
    merged_data = {}
    for field_name in ProcurementListing.model_fields:
        orig_val = getattr(original, field_name)
        detail_val = getattr(detail, field_name)
        # Keep original title always; for other fields, prefer detail if original is None
        if field_name == "title":
            merged_data[field_name] = orig_val
        elif orig_val is None and detail_val is not None:
            merged_data[field_name] = detail_val
        else:
            merged_data[field_name] = orig_val
    return ProcurementListing(**merged_data)


async def _enrich_with_details(
    listings: list[ProcurementListing],
    browser,
    portal: "PortalRecord",
) -> list[ProcurementListing]:
    """
    Enrich sparse listings by visiting their detail pages.

    For each listing that has a source_url and is sparse (missing description,
    closing_date, and value_min), navigates to the detail page, extracts full
    details, and merges them back into the listing.

    Respects config.BROWSER_DETAIL_MAX_PAGES to limit the number of detail
    page visits per scrape run.

    Args:
        listings: List of ProcurementListing objects from the listing page.
        browser: The browser-use Browser instance (kept alive).
        portal: The portal record for URL resolution and naming.

    Returns:
        Updated list of ProcurementListing objects with enriched details.
    """
    sparse_listings = [
        (i, listing)
        for i, listing in enumerate(listings)
        if listing.source_url and _is_sparse(listing)
    ]

    if not sparse_listings:
        logger.info(
            "Portal '%s': no sparse listings with URLs to enrich",
            portal.name,
        )
        return listings

    max_pages = config.BROWSER_DETAIL_MAX_PAGES
    to_enrich = sparse_listings[:max_pages]

    logger.info(
        "Portal '%s': enriching %d/%d sparse listings (max %d)",
        portal.name,
        len(to_enrich),
        len(sparse_listings),
        max_pages,
    )

    enriched = list(listings)  # shallow copy

    for idx, (orig_index, listing) in enumerate(to_enrich):
        detail_url = _resolve_url(listing.source_url, portal.url)

        try:
            page = await browser.get_current_page()
            if page is None:
                logger.warning(
                    "Portal '%s': lost browser page during enrichment",
                    portal.name,
                )
                break

            await page.goto(detail_url)
            # browser-use pages lack wait_for_load_state; brief
            # pause lets the page content settle before extraction.
            await asyncio.sleep(3)

            html_content = await page.evaluate(
                "() => document.documentElement.outerHTML"
            )

            detail = extract_listing_detail(html_content, portal.name)

            if detail is not None:
                enriched[orig_index] = _merge_detail(listing, detail)
                logger.info(
                    "Portal '%s': enriched listing '%s' from detail page (%d/%d)",
                    portal.name,
                    listing.title,
                    idx + 1,
                    len(to_enrich),
                )
            else:
                logger.warning(
                    "Portal '%s': detail extraction returned None for '%s'",
                    portal.name,
                    listing.title,
                )
        except Exception:
            logger.exception(
                "Portal '%s': failed to enrich listing '%s' from %s",
                portal.name,
                listing.title,
                detail_url,
            )

    return enriched


async def browser_scrape(
    portal: PortalRecord,
    keywords_by_category: dict[str, dict[str, list[str]]] | None = None,
) -> BrowserScrapeResult:
    """
    Scrape a generic procurement portal for listings.

    When keywords_by_category is None, uses a broad AI navigation prompt to
    find the listing page on any portal layout (no-keyword path).

    When keywords_by_category is provided, the agent searches for keywords
    using the portal's search form. Uses OR queries first, falling back to
    single keywords if OR returns no results. Action history is inspected
    to detect whether a search was actually performed.

    Args:
        portal: The portal record with URL and metadata.
        keywords_by_category: Optional dict of category -> {lang -> [keywords]}.
            When provided, enables keyword search path.

    Returns:
        BrowserScrapeResult with listings and search_used flag.
        Returns empty result on any failure (error isolation).
    """
    # Lazy import: browser-use requires Python 3.11+ and Playwright.
    # These are available in the Docker runtime but may not be in dev/test.
    try:
        from browser_use import Agent, Browser, BrowserProfile, ChatOpenAI
    except ImportError:
        logger.error(
            "browser-use not installed. "
            "Generic browser scraping requires Python 3.11+ with "
            "browser-use package."
        )
        return BrowserScrapeResult(listings=[], search_used=False)

    logger.info(
        "Starting browser scrape for '%s' at %s",
        portal.name,
        portal.url,
    )

    browser = None
    try:
        if keywords_by_category is None or not keywords_by_category:
            # --- No-keyword path (original behavior) ---
            browser = Browser(
                browser_profile=BrowserProfile(
                    headless=config.BROWSER_HEADLESS,
                    minimum_wait_page_load_time=config.BROWSER_WAIT_NETWORK_IDLE,
                    wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS,
                    enable_default_extensions=False,
                ),
                keep_alive=True,
            )

            agent = Agent(
                task=(
                    f"Navigate to {portal.url}. "
                    f"Find the page that lists open procurement opportunities, "
                    f"tenders, or bids. Look for a listing page with multiple "
                    f"opportunities. Do not click on individual listings. "
                    f"Do not fill in search forms. Stop once you can see a "
                    f"list of opportunities."
                ),
                llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
                browser=browser,
                use_vision=False,
            )

            history = await agent.run(max_steps=config.BROWSER_MAX_STEPS)

            page = await browser.get_current_page()

            if page is None:
                logger.error(
                    "Could not access browser page for portal '%s'",
                    portal.name,
                )
                return BrowserScrapeResult(listings=[], search_used=False)

            html_content = await page.evaluate("() => document.documentElement.outerHTML")
            page_url = await page.evaluate("() => window.location.href")

            listings = extract_listings_from_html(html_content, portal.name)
            listings = _fix_source_urls(listings, page_url, portal.url)

            # Enrich sparse listings by visiting detail pages
            listings = await _enrich_with_details(listings, browser, portal)

            steps_used = history.number_of_steps() if history else 0
            logger.info(
                "Browser scrape complete for '%s' (%s): "
                "%d listings found, %d agent steps used",
                portal.name,
                portal.url,
                len(listings),
                steps_used,
            )

            return BrowserScrapeResult(listings=listings, search_used=False)

        else:
            # --- Keyword search path ---
            # Build keyword batches
            batches = []
            for cat_name, cat_kw in keywords_by_category.items():
                batch = select_keyword_batch(cat_kw)
                if batch:
                    batches.append((cat_name, batch))

            if not batches:
                # Edge case: all categories empty after batch selection
                # Fall through to no-keyword behavior
                browser = Browser(
                    browser_profile=BrowserProfile(
                        headless=config.BROWSER_HEADLESS,
                        minimum_wait_page_load_time=config.BROWSER_WAIT_NETWORK_IDLE,
                        wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS,
                        enable_default_extensions=False,
                    ),
                    keep_alive=True,
                )
                agent = Agent(
                    task=(
                        f"Navigate to {portal.url}. "
                        f"Find the page that lists open procurement opportunities, "
                        f"tenders, or bids. Look for a listing page with multiple "
                        f"opportunities. Do not click on individual listings. "
                        f"Do not fill in search forms. Stop once you can see a "
                        f"list of opportunities."
                    ),
                    llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
                    browser=browser,
                    use_vision=False,
                )
                history = await agent.run(max_steps=config.BROWSER_MAX_STEPS)
                page = await browser.get_current_page()
                if page is None:
                    return BrowserScrapeResult(listings=[], search_used=False)
                html_content = await page.evaluate("() => document.documentElement.outerHTML")
                page_url = await page.evaluate("() => window.location.href")
                listings = extract_listings_from_html(html_content, portal.name)
                listings = _fix_source_urls(listings, page_url, portal.url)
                listings = await _enrich_with_details(listings, browser, portal)
                return BrowserScrapeResult(listings=listings, search_used=False)

            all_listings: list[ProcurementListing] = []
            search_detected = False
            total_steps = 0
            or_supported = True
            searches_completed = 0

            browser = Browser(
                browser_profile=BrowserProfile(
                    headless=config.BROWSER_HEADLESS,
                    minimum_wait_page_load_time=config.BROWSER_WAIT_NETWORK_IDLE,
                    wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS,
                    enable_default_extensions=False,
                ),
                keep_alive=True,
            )

            for i, (cat_name, batch) in enumerate(batches):
                remaining_budget = config.BROWSER_SEARCH_MAX_STEPS - total_steps
                if remaining_budget <= 0:
                    logger.warning(
                        "Step budget exhausted (%d/%d) for '%s' after %d/%d searches",
                        total_steps, config.BROWSER_SEARCH_MAX_STEPS,
                        portal.name, searches_completed, len(batches),
                    )
                    break

                # Build query based on OR support
                if or_supported:
                    query = " OR ".join(batch)
                else:
                    query = batch[0]

                # Build agent task
                if i == 0:
                    task = (
                        f"Navigate to {portal.url}. "
                        f"Look for a search form, search box, or Advanced Search page for "
                        f"procurement opportunities, tenders, or bids. "
                        f"If you see a 'Search' or 'Advanced Search' link, click on it. "
                        f"If there's a hidden search bar (magnifying glass icon or expandable panel), "
                        f"click to reveal it. "
                        f"Once you find a search input, type: {query} "
                        f"Submit the search by pressing Enter or clicking the search/submit button. "
                        f"Stop when you can see search results or a list of opportunities."
                    )
                    max_steps = min(remaining_budget, 20)
                else:
                    task = (
                        f"On this page, find the search box or search input. "
                        f"Clear any existing text in it. "
                        f"Type: {query} "
                        f"Submit the search by pressing Enter or clicking the search/submit button. "
                        f"Stop when you can see search results."
                    )
                    max_steps = min(remaining_budget, 8)

                try:
                    agent = Agent(
                        task=task,
                        llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
                        browser=browser,
                        use_vision=False,
                    )
                    history = await agent.run(max_steps=max_steps)

                    steps_used = history.number_of_steps() if history else 0
                    total_steps += steps_used

                    if _detect_search_used(history):
                        search_detected = True

                    page = await browser.get_current_page()
                    if page is not None:
                        html = await page.evaluate("() => document.documentElement.outerHTML")
                        page_url = await page.evaluate("() => window.location.href")
                        listings = extract_listings_from_html(html, portal.name)
                        listings = _fix_source_urls(listings, page_url, portal.url)

                        if or_supported and not listings and search_detected:
                            or_supported = False
                            query = batch[0]
                            logger.info(
                                "OR query returned 0 results for '%s' category '%s', "
                                "falling back to single keyword: '%s'",
                                portal.name, cat_name, query,
                            )
                            remaining_budget = config.BROWSER_SEARCH_MAX_STEPS - total_steps
                            if remaining_budget > 0:
                                retry_agent = Agent(
                                    task=(
                                        f"Clear the search box. Type: {query} "
                                        f"Submit the search. Stop when you see results."
                                    ),
                                    llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
                                    browser=browser,
                                    use_vision=False,
                                )
                                retry_history = await retry_agent.run(
                                    max_steps=min(remaining_budget, 8)
                                )
                                total_steps += retry_history.number_of_steps() if retry_history else 0
                                page = await browser.get_current_page()
                                if page is not None:
                                    html = await page.evaluate("() => document.documentElement.outerHTML")
                                    page_url = await page.evaluate("() => window.location.href")
                                    listings = extract_listings_from_html(html, portal.name)
                                    listings = _fix_source_urls(listings, page_url, portal.url)

                        all_listings.extend(listings)
                        searches_completed += 1

                        logger.info(
                            "Portal '%s' category '%s': %d listings found (%s query, %d steps)",
                            portal.name, cat_name, len(listings),
                            "OR" if or_supported else "single",
                            steps_used,
                        )

                except Exception:
                    logger.exception(
                        "Search failed for portal '%s' category '%s'",
                        portal.name, cat_name,
                    )

            if not search_detected:
                logger.info(
                    "No search form detected for '%s', returning visible listings (fallback)",
                    portal.name,
                )

            deduplicated = deduplicate_listings(all_listings)

            # Enrich sparse listings by visiting detail pages
            deduplicated = await _enrich_with_details(
                deduplicated, browser, portal
            )

            logger.info(
                "Browser keyword search complete for '%s': "
                "%d/%d searches completed, %d total listings, %d after dedup, "
                "%d steps used, search_used=%s",
                portal.name, searches_completed, len(batches),
                len(all_listings), len(deduplicated),
                total_steps, search_detected,
            )

            return BrowserScrapeResult(listings=deduplicated, search_used=search_detected)

    except Exception:
        logger.exception(
            "Browser scrape failed for portal '%s' (%s)",
            portal.name,
            portal.url,
        )
        return BrowserScrapeResult(listings=[], search_used=False)

    finally:
        if browser is not None:
            try:
                await browser.kill()
            except Exception:
                logger.warning(
                    "Failed to close browser for portal '%s'",
                    portal.name,
                )
