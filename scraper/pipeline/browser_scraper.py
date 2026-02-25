"""
Generic browser scraper for diverse procurement portals.

Handles portals that are NOT CanadaBuys or BidsAndTenders. Uses browser-use
Agent with a broad navigation prompt to find and extract procurement listings
from any portal layout.

Uses browser-use Agent for navigation (headless=False to avoid 403 blocks)
and delegates HTML extraction to the extraction module.
"""

import logging

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.extraction import extract_listings_from_html

logger = logging.getLogger(__name__)


async def browser_scrape(
    portal: PortalRecord,
) -> list[ProcurementListing]:
    """
    Scrape a generic procurement portal for listings.

    Uses a broad AI navigation prompt to find the listing page on any
    portal layout. The Agent navigates to find open procurement opportunities
    without clicking into individual listings or filling search forms.

    Args:
        portal: The portal record with URL and metadata.

    Returns:
        List of ProcurementListing objects extracted from the page.
        Returns empty list on any failure (error isolation).
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
        return []

    logger.info(
        "Starting browser scrape for '%s' at %s",
        portal.name,
        portal.url,
    )

    browser = None
    try:
        # Create browser with standard wait times
        # headless=False is REQUIRED -- POC confirmed headless=True gets 403-blocked
        browser = Browser(
            browser_profile=BrowserProfile(
                headless=config.BROWSER_HEADLESS,
                minimum_wait_page_load_time=config.BROWSER_WAIT_NETWORK_IDLE,
                wait_between_actions=config.BROWSER_WAIT_BETWEEN_ACTIONS,
            )
        )

        # Create navigation agent with broad prompt for diverse portals
        # browser-use 0.11 requires its own ChatOpenAI wrapper (not langchain's)
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

        # Run the navigation agent
        history = await agent.run(max_steps=config.BROWSER_MAX_STEPS)

        # Get page HTML from the browser's current page
        page = None
        browser_context = None
        try:
            browser_context = await browser.new_context()
            page = await browser_context.get_current_page()
        except (AttributeError, TypeError):
            # Fallback for different browser-use versions
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

        steps_used = history.number_of_steps() if history else 0
        logger.info(
            "Browser scrape complete for '%s' (%s): "
            "%d listings found, %d agent steps used",
            portal.name,
            portal.url,
            len(listings),
            steps_used,
        )

        return listings

    except Exception:
        logger.exception(
            "Browser scrape failed for portal '%s' (%s)",
            portal.name,
            portal.url,
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
