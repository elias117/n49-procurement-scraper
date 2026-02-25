"""
BidsAndTenders platform scraper.

Handles ~20 procurement portals that share the BidsAndTenders platform.
All share an identical structure with the pattern: {base_url}/Module/Tenders/en.

Uses Playwright directly (not browser-use Agent) since the URL pattern is
known and no AI navigation is needed. headless=False under Xvfb avoids 403s.

Supports keyword search via the portal's search box: builds OR queries from
random keyword batches per category, with individual-keyword fallback when
OR queries return zero results.
"""

from __future__ import annotations

import logging
from typing import NamedTuple
from urllib.parse import urlparse

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.extraction import extract_listings_from_html
from scraper.pipeline.keywords import select_keyword_batch, deduplicate_listings

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class BidsAndTendersResult(NamedTuple):
    """Result from a BidsAndTenders scrape with search metadata."""
    listings: list[ProcurementListing]
    search_used: bool  # True if keyword search was performed, False if fell back to full scrape


async def _find_search_input(page):
    """
    Try to find a visible search input on the page.

    Tries selectors in order: searchbox role, "Search" placeholder, first text input.
    Returns the first visible locator, or None if none found.
    """
    # Try searchbox role
    try:
        locator = page.get_by_role("searchbox")
        if await locator.is_visible(timeout=3000):
            return locator
    except Exception:
        pass

    # Try placeholder
    try:
        locator = page.get_by_placeholder("Search")
        if await locator.is_visible(timeout=3000):
            return locator
    except Exception:
        pass

    # Try first text input
    try:
        locator = page.locator("input[type='text']").first
        if await locator.is_visible(timeout=3000):
            return locator
    except Exception:
        pass

    logger.warning("No search input found on the page")
    return None


async def _execute_search(page, search_input, query: str) -> str:
    """
    Execute a search query using the provided search input locator.

    Clears existing text, fills with query, presses Enter, waits for results.
    Returns the page HTML content after the search completes.
    """
    await search_input.fill("")
    await search_input.fill(query)
    await search_input.press("Enter")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(3000)
    return await page.content()


async def _reset_search(page, listing_url: str) -> None:
    """
    Reset the search state on the page.

    Tries to click a "Reset" button if visible. Falls back to navigating
    back to the listing URL.
    """
    try:
        reset_btn = page.get_by_text("Reset", exact=False)
        if await reset_btn.is_visible(timeout=2000):
            await reset_btn.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
            return
    except Exception:
        pass

    # Fallback: navigate back to listing URL
    await page.goto(listing_url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)


async def bidsandtenders_scrape(
    portal: PortalRecord,
    keywords_by_category: dict[str, dict[str, list[str]]] | None = None,
) -> BidsAndTendersResult:
    """
    Scrape a BidsAndTenders portal for procurement listings.

    All BidsAndTenders portals share the same structure. The tender listing
    page is always at {base_url}/Module/Tenders/en.

    When keywords_by_category is provided and a search box is found,
    performs keyword searches (OR queries with individual fallback) and
    returns search_used=True. Otherwise falls back to full page scrape
    with search_used=False.

    Args:
        portal: The portal record with URL and metadata.
        keywords_by_category: Optional category->language->keywords dict.

    Returns:
        BidsAndTendersResult with listings and search_used flag.
    """
    if async_playwright is None:
        logger.error(
            "playwright not installed. "
            "BidsAndTenders scraping requires playwright package."
        )
        return BidsAndTendersResult(listings=[], search_used=False)

    # Construct the standard tender listing URL
    parsed = urlparse(portal.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    listing_url = f"{base_url}/Module/Tenders/en"

    logger.info(
        "Starting BidsAndTenders scrape for '%s' at %s",
        portal.name,
        listing_url,
    )

    browser = None
    try:
        p = await async_playwright().start()

        # headless=False is REQUIRED -- POC confirmed headless=True gets 403-blocked
        # Runs under Xvfb in Docker for virtual display
        browser = await p.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # Navigate and wait for network to settle (AJAX table load)
        await page.goto(listing_url, wait_until="networkidle", timeout=30000)

        # Extra wait for AJAX content that loads after networkidle
        await page.wait_for_timeout(5000)

        # Determine if we can use keyword search
        search_input = await _find_search_input(page) if keywords_by_category else None

        if search_input is None:
            # Fall back to original behavior: scrape full page
            html_content = await page.content()

            logger.info(
                "Page loaded for '%s', HTML length: %d",
                portal.name,
                len(html_content),
            )

            listings = extract_listings_from_html(html_content, portal.name)

            logger.info(
                "BidsAndTenders scrape complete for '%s': %d listings found (full scrape)",
                portal.name,
                len(listings),
            )

            return BidsAndTendersResult(listings=listings, search_used=False)

        # --- Keyword search path ---

        # Try to set results limit to 100
        try:
            limit_option = page.get_by_text("100")
            if await limit_option.is_visible(timeout=2000):
                await limit_option.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
                # Re-find search input after page reload
                search_input = await _find_search_input(page)
        except Exception:
            pass  # Continue with default limit

        all_listings: list[ProcurementListing] = []
        or_supported = True

        for category_name, category_keywords in keywords_by_category.items():
            batch = select_keyword_batch(category_keywords)

            if not batch:
                continue

            if or_supported:
                # Try OR query
                or_query = " OR ".join(batch)
                html = await _execute_search(page, search_input, or_query)
                listings = extract_listings_from_html(html, portal.name)

                if listings:
                    all_listings.extend(listings)
                    logger.info(
                        "Category '%s' OR query returned %d listings",
                        category_name,
                        len(listings),
                    )
                    await _reset_search(page, listing_url)
                    # Re-find search input after reset
                    search_input = await _find_search_input(page)
                    continue
                else:
                    # OR not supported, fall through to individual
                    or_supported = False
                    logger.info(
                        "OR query returned 0 results for category '%s', "
                        "falling back to individual keyword searches",
                        category_name,
                    )

            # Individual keyword fallback
            for keyword in batch:
                await _reset_search(page, listing_url)
                # Re-find search input after reset
                search_input = await _find_search_input(page)
                if search_input is None:
                    break
                html = await _execute_search(page, search_input, keyword)
                listings = extract_listings_from_html(html, portal.name)
                all_listings.extend(listings)

            # Reset after each category
            await _reset_search(page, listing_url)
            search_input = await _find_search_input(page)

        # Deduplicate across all categories
        deduplicated = deduplicate_listings(all_listings)

        logger.info(
            "BidsAndTenders keyword search complete for '%s': "
            "%d total, %d after dedup",
            portal.name,
            len(all_listings),
            len(deduplicated),
        )

        return BidsAndTendersResult(listings=deduplicated, search_used=True)

    except Exception:
        logger.exception(
            "BidsAndTenders scrape failed for portal '%s' (%s)",
            portal.name,
            listing_url,
        )
        return BidsAndTendersResult(listings=[], search_used=False)

    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.warning(
                    "Failed to close browser for portal '%s'",
                    portal.name,
                )
        try:
            await p.stop()
        except Exception:
            pass
