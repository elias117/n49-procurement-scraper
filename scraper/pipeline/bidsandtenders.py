"""
BidsAndTenders platform scraper.

Handles ~20 procurement portals that share the BidsAndTenders platform.
All share an identical structure with the pattern: {base_url}/Module/Tenders/en.

Uses browser-use Agent for navigation (headless=False to avoid 403 blocks)
and delegates HTML extraction to the extraction module.
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
    page is always at {base_url}/Module/Tenders/en. Navigation waits 3s
    for AJAX content to load (pitfall: table loads after initial page render).

    Args:
        portal: The portal record with URL and metadata.

    Returns:
        List of ProcurementListing objects extracted from the page.
        Returns empty list on any failure (error isolation).
    """
    # Lazy import: browser-use requires Python 3.11+ and Playwright.
    # These are available in the Docker runtime but may not be in dev/test.
    try:
        from browser_use import Agent, Browser, BrowserProfile
        from langchain_openai import ChatOpenAI
    except ImportError:
        logger.error(
            "browser-use or langchain-openai not installed. "
            "BidsAndTenders scraping requires Python 3.11+ with "
            "browser-use and langchain-openai packages."
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
        # Create browser with extended AJAX wait time
        # headless=False is REQUIRED -- POC confirmed headless=True gets 403-blocked
        browser = Browser(
            browser_profile=BrowserProfile(
                headless=config.BROWSER_HEADLESS,
                minimum_wait_page_load_time=3.0,
                wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS,
            )
        )

        # Create navigation agent
        agent = Agent(
            task=(
                f"Navigate to {listing_url}. "
                f"Wait for the tender listing table to load. "
                f"The table loads via AJAX after the page renders. "
                f"Do not click on individual tenders. "
                f"Do not navigate away from this page."
            ),
            llm=ChatOpenAI(model=config.OPENAI_EXTRACTION_MODEL),
            browser=browser,
            max_actions_per_step=4,
            max_failures=3,
            use_vision=False,
            max_steps=config.BROWSER_MAX_STEPS,
        )

        # Run the navigation agent
        history = await agent.run(max_steps=config.BROWSER_MAX_STEPS)

        # Get page HTML via the browser's current page
        # browser-use exposes the Playwright page through the browser context
        page = None
        if hasattr(browser, "current_page"):
            page = browser.current_page
        elif hasattr(browser, "context") and browser.context:
            pages = browser.context.pages
            if pages:
                page = pages[-1]

        if page is None:
            logger.error(
                "Could not access browser page for portal '%s'",
                portal.name,
            )
            return []

        html_content = await page.content()

        # Extract structured listings from the HTML
        listings = extract_listings_from_html(html_content, portal.name)

        # Tag each listing with the source portal
        for listing in listings:
            listing.source_portal = portal.id

        steps_used = len(history) if history else 0
        logger.info(
            "BidsAndTenders scrape complete for '%s': "
            "%d listings found, %d agent steps used",
            portal.name,
            len(listings),
            steps_used,
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
