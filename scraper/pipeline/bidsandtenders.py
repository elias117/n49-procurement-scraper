"""
BidsAndTenders platform scraper.

Handles ~20 procurement portals that share the BidsAndTenders platform.
All share an identical structure with the pattern: {base_url}/Module/Tenders/en.

Uses Playwright directly (not browser-use Agent) since the URL pattern is
known and no AI navigation is needed. headless=False under Xvfb avoids 403s.
"""

import logging
from urllib.parse import urlparse

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.extraction import extract_listings_from_html

logger = logging.getLogger(__name__)


async def bidsandtenders_scrape(
    portal: PortalRecord,
) -> list[ProcurementListing]:
    """
    Scrape a BidsAndTenders portal for procurement listings.

    All BidsAndTenders portals share the same structure. The tender listing
    page is always at {base_url}/Module/Tenders/en.

    Uses Playwright directly instead of browser-use Agent because:
    - URL pattern is known (no AI navigation needed)
    - Avoids browser-use session lifecycle issues (session resets on agent done)
    - Simpler, faster, and no LLM API cost for navigation

    Args:
        portal: The portal record with URL and metadata.

    Returns:
        List of ProcurementListing objects extracted from the page.
        Returns empty list on any failure (error isolation).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "playwright not installed. "
            "BidsAndTenders scraping requires playwright package."
        )
        return []

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

        html_content = await page.content()

        logger.info(
            "Page loaded for '%s', HTML length: %d",
            portal.name,
            len(html_content),
        )

        # Extract structured listings from the HTML
        listings = extract_listings_from_html(html_content, portal.name)

        logger.info(
            "BidsAndTenders scrape complete for '%s': %d listings found",
            portal.name,
            len(listings),
        )

        return listings

    except Exception:
        logger.exception(
            "BidsAndTenders scrape failed for portal '%s' (%s)",
            portal.name,
            listing_url,
        )
        return []

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
