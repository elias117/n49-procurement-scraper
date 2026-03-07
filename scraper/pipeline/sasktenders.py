"""SaskTenders scraper."""

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
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SASKTENDERS_URL = "https://www.sasktenders.ca/"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _parse_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    text = re.sub(r"\s+[A-Z]{2,4}$", "", text)

    for fmt in (
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _extract_competition_type(detail_block) -> str | None:
    for header in detail_block.select("th"):
        label = _normalize_text(header.get_text(" "))
        if label and "competition type" in label.lower():
            value_cell = header.find_next("td")
            if value_cell:
                return _normalize_text(value_cell.get_text(" "))
    return None


def _extract_print_url(detail_block, page_url: str) -> str | None:
    link = detail_block.select_one("a[href*='print.aspx?competitionId=']")
    if link and link.get("href"):
        return urljoin(page_url, link["href"])
    return None


def _extract_header_cells(header_block) -> list[str]:
    row = header_block.select_one("table.ContentAccordionFormat tr")
    if not row:
        return []

    cells = [_normalize_text(td.get_text(" ")) or "" for td in row.select("td")]
    # Cell 0 is the accordion icon spacer.
    return cells


def _extract_sasktenders_listings(html_content: str, page_url: str) -> list[ProcurementListing]:
    soup = BeautifulSoup(html_content, "html.parser")

    listings: list[ProcurementListing] = []

    for header_block in soup.select("div.HeaderAccordionPlusFormat"):
        detail_block = header_block.find_next_sibling("div", class_="ContentAccordionFormat_SearchPage")
        if detail_block is None:
            continue

        cells = _extract_header_cells(header_block)
        if len(cells) < 7:
            continue

        title = _normalize_text(cells[1])
        organization = _normalize_text(cells[2])
        reference_number = _normalize_text(cells[3])
        open_date = _parse_date(cells[4])
        close_date = _parse_date(cells[5])
        status = _normalize_text(cells[6]) or "Open"

        if not title:
            continue

        category = _extract_competition_type(detail_block)
        source_url = _extract_print_url(detail_block, page_url) or page_url

        description_parts = []
        if organization:
            description_parts.append(f"Organization: {organization}")
        if category:
            description_parts.append(f"Category: {category}")

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=reference_number,
                description=" | ".join(description_parts) if description_parts else None,
                posting_date=open_date,
                closing_date=close_date,
                source_url=source_url,
                source_listing_id=reference_number or source_url,
                status=status,
                raw_location=organization,
            )
        )

    return listings


async def sasktenders_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape public competitions from SaskTenders."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty SaskTenders listing set")
        return []

    url = portal.url or SASKTENDERS_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(2000)

        html_content = await page.content()
        listings = _extract_sasktenders_listings(html_content, page.url or url)
        listings = deduplicate_listings(listings)

        logger.info("Portal '%s': SaskTenders scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': SaskTenders scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
