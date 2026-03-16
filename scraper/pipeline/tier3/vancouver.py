"""City of Vancouver bids portal scraper."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.keywords import deduplicate_listings

try:
    from playwright.async_api import Page, async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    Page = object  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

VANCOUVER_URL = "https://vancouver.ca/doing-business/bids-contracts-rfps-and-supplier-portal.aspx"
VANCOUVER_OPEN_BIDS_URL = "https://bids.vancouver.ca/bidopp/openbid.htm"
VANCOUVER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _parse_vancouver_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    # Extract either date+time or date token from verbose detail text.
    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)", text, flags=re.IGNORECASE)
    if match:
        token = match.group(1).upper()
        for fmt in ("%d/%m/%Y %I:%M %p", "%m/%d/%Y %I:%M %p"):
            try:
                return datetime.strptime(token, fmt).date().isoformat()
            except ValueError:
                continue

    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", text)
    if match:
        token = match.group(1)
        for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(token, fmt).date().isoformat()
            except ValueError:
                continue

    return None


def _extract_reference_from_source_url(source_url: str | None) -> str | None:
    text = _normalize_text(source_url)
    if not text:
        return None

    match = re.search(r"[?&]eventid=(\d+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _extract_vancouver_listings(html_content: str, page_url: str) -> list[ProcurementListing]:
    soup = BeautifulSoup(html_content, "html.parser")
    listings: list[ProcurementListing] = []

    for row in soup.select("table.table.phx.table-hover.no-column-borders tr"):
        columns = row.select("td")
        if len(columns) < 2:
            continue

        status = _normalize_text(columns[0].get_text(" "))
        if status and "open" not in status.lower():
            continue

        details_col = columns[1]
        title_anchor = details_col.select_one("a[href*='ViewSourcingEvent']")
        title = _normalize_text(title_anchor.get_text(" ") if title_anchor else None)
        if not title:
            continue

        source_url = urljoin(page_url, title_anchor.get("href")) if title_anchor else page_url
        details_text = _normalize_text(details_col.get_text(" ")) or ""

        reference_match = re.search(r"\bNumber\s+([A-Za-z0-9\-]+)\b", details_text)
        reference_number = _normalize_text(reference_match.group(1) if reference_match else None)
        category_match = re.search(r"\bType\s+(.+?)\s+Number\b", details_text)
        category = _normalize_text(category_match.group(1) if category_match else None)

        open_match = re.search(
            r"\bOpen\s+(\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)",
            details_text,
            flags=re.IGNORECASE,
        )
        close_match = re.search(
            r"\bClose\s+(\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)",
            details_text,
            flags=re.IGNORECASE,
        )

        posting_date = _parse_vancouver_date(open_match.group(1) if open_match else None)
        closing_date = _parse_vancouver_date(close_match.group(1) if close_match else None)

        description_parts = []
        if category:
            description_parts.append(f"Category: {category}")
        if status:
            description_parts.append(f"Status: {status}")

        source_listing_id = (
            reference_number
            or _extract_reference_from_source_url(source_url)
            or source_url
        )

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=reference_number,
                description=" | ".join(description_parts) if description_parts else None,
                posting_date=posting_date,
                closing_date=closing_date,
                source_url=source_url,
                source_listing_id=source_listing_id,
                status="Open",
                raw_location="Vancouver, British Columbia",
            )
        )

    return listings


async def _open_vancouver_listings_page(page: Page, start_url: str) -> str:
    await page.goto(start_url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(6000)

    current_url = page.url or start_url
    if "bids.sciquest.com" in current_url.lower():
        return current_url

    open_link = page.locator("a[href*='bids.vancouver.ca/bidopp/openbid.htm']").first
    if await open_link.count():
        href = await open_link.get_attribute("href")
        target = urljoin(page.url or start_url, href) if href else VANCOUVER_OPEN_BIDS_URL
        await page.goto(target, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)
        return page.url or target

    await page.goto(VANCOUVER_OPEN_BIDS_URL, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(8000)
    return page.url or VANCOUVER_OPEN_BIDS_URL


async def vancouver_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape Vancouver open opportunities from the current Jaggaer public page."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty Vancouver listing set")
        return []

    url = portal.url or VANCOUVER_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=VANCOUVER_USER_AGENT,
        )
        page = await context.new_page()

        final_url = await _open_vancouver_listings_page(page, url)
        html_content = await page.content()

        listings = _extract_vancouver_listings(html_content, final_url)
        listings = deduplicate_listings(listings)

        logger.info("Portal '%s': Vancouver scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': Vancouver scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
