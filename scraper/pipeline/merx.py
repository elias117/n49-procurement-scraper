"""
MERX family scraper.

Scrapes public open-bids pages for MERX tenants and extracts listing metadata.
"""

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

MERX_DEFAULT_URL = "https://www.merx.com/"


def _normalize_merx_listing_url(portal_url: str) -> str:
    """Return the tenant open-bids listing URL for a MERX portal URL."""
    base = portal_url.strip() or MERX_DEFAULT_URL
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"

    base = base.rstrip("/")
    if not base:
        base = MERX_DEFAULT_URL.rstrip("/")

    return f"{base}/solicitations/open-bids"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _parse_merx_date(value: str | None) -> str | None:
    """Parse MERX date strings to ISO date format."""
    text = _normalize_text(value)
    if not text:
        return None

    # Most MERX listing pages expose YYYY/MM/DD for Published/Closing.
    match = re.search(r"(\d{4}/\d{2}/\d{2})", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y/%m/%d").date().isoformat()
        except ValueError:
            pass

    # Some views can show day-first dates.
    match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    if match:
        for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(match.group(1), fmt).date().isoformat()
            except ValueError:
                continue

    return None


def _extract_listing_id(reference_number: str | None, source_url: str | None) -> str | None:
    if reference_number:
        return reference_number
    if not source_url:
        return None

    # MERX detail URLs commonly include an ID token at the end.
    match = re.search(r"/(\d{6,})(?:\?|$)", source_url)
    if match:
        return match.group(1)

    return source_url


def _build_listing_from_row(row, page_url: str) -> ProcurementListing | None:
    link = row.select_one("a.solicitation-link[href]")
    if not link:
        return None

    title = _normalize_text(link.get_text(" "))
    if not title:
        return None

    href = _normalize_text(link.get("href"))
    source_url = urljoin(page_url, href) if href else page_url

    reference_number = _normalize_text(
        (row.select_one(".sol-num") or row.select_one(".sol-number") or row.select_one(".sol-ref")).get_text(" ")
        if row.select_one(".sol-num") or row.select_one(".sol-number") or row.select_one(".sol-ref")
        else None
    )

    organization = _normalize_text(
        (row.select_one(".sol-buyer-name") or row.select_one(".sol-region-item")).get_text(" ")
        if row.select_one(".sol-buyer-name") or row.select_one(".sol-region-item")
        else None
    )

    category = _normalize_text(
        (row.select_one(".sol-category") or row.select_one(".sol-categories") or row.select_one(".sol-type")).get_text(" ")
        if row.select_one(".sol-category") or row.select_one(".sol-categories") or row.select_one(".sol-type")
        else None
    )

    closing_text = _normalize_text(
        (row.select_one(".sol-closing-date .date-value") or row.select_one(".sol-close-date .date-value") or row.select_one(".sol-closing-date")).get_text(" ")
        if row.select_one(".sol-closing-date .date-value")
        or row.select_one(".sol-close-date .date-value")
        or row.select_one(".sol-closing-date")
        else None
    )

    posted_text = _normalize_text(
        (row.select_one(".sol-publication-date .date-value") or row.select_one(".sol-publication-date")).get_text(" ")
        if row.select_one(".sol-publication-date .date-value") or row.select_one(".sol-publication-date")
        else None
    )

    description_parts = []
    if organization:
        description_parts.append(f"Organization: {organization}")
    if category:
        description_parts.append(f"Category: {category}")

    return ProcurementListing(
        title=title,
        reference_number=reference_number,
        description=" | ".join(description_parts) if description_parts else None,
        posting_date=_parse_merx_date(posted_text),
        closing_date=_parse_merx_date(closing_text),
        source_url=source_url,
        source_listing_id=_extract_listing_id(reference_number, source_url),
        status="Open",
        raw_location=organization,
    )


def _extract_current_page_listings(html_content: str, page_url: str) -> list[ProcurementListing]:
    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.select("tr.mets-table-row")

    listings: list[ProcurementListing] = []
    for row in rows:
        listing = _build_listing_from_row(row, page_url)
        if listing is not None:
            listings.append(listing)

    return listings


def _extract_pagination_urls(html_content: str, page_url: str) -> list[str]:
    """Extract all available MERX page URLs from the page select control."""
    soup = BeautifulSoup(html_content, "html.parser")
    urls: list[str] = []

    for option in soup.select("select[id^='pagination_select_'] option[data-href]"):
        href = _normalize_text(option.get("data-href"))
        if href:
            urls.append(urljoin(page_url, href))

    return urls


async def _collect_listing_pages(page: Page, start_url: str, portal_name: str) -> list[str]:
    """Discover MERX pagination URLs from the first page and return unique page URLs."""
    await page.goto(start_url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(2000)

    current_url = page.url or start_url
    html_content = await page.content()

    discovered = [current_url]
    for url in _extract_pagination_urls(html_content, current_url):
        if url not in discovered:
            discovered.append(url)

    logger.info("Portal '%s': discovered %d MERX pages", portal_name, len(discovered))
    return discovered


async def merx_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape public open-bids listings from a MERX tenant portal."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty list for MERX")
        return []

    listing_url = _normalize_merx_listing_url(portal.url)
    listings: list[ProcurementListing] = []

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        page_urls = await _collect_listing_pages(page, listing_url, portal.name)

        for page_url in page_urls:
            try:
                await page.goto(page_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(1500)
                html_content = await page.content()
                listings.extend(_extract_current_page_listings(html_content, page.url or page_url))
            except Exception:
                logger.exception(
                    "Portal '%s': failed to scrape MERX page %s",
                    portal.name,
                    page_url,
                )

        listings = deduplicate_listings(listings)
        logger.info("Portal '%s': MERX scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': MERX scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
