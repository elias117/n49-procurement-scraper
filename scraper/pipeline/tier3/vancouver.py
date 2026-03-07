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
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

VANCOUVER_URL = "https://bids.vancouver.ca/"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _parse_vancouver_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    # Remove trailing timezone abbrev to simplify parsing.
    text = re.sub(r"\s+[A-Z]{2,4}$", "", text)

    for fmt in (
        "%d/%m/%Y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _extract_metadata_map(container) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for row in container.select(".phx.table-row-layout"):
        key_elem = row.select_one(".data-row-name")
        value_elem = row.select_one(".data-row-content")
        if not key_elem or not value_elem:
            continue

        key = _normalize_text(key_elem.get_text(" "))
        value = _normalize_text(value_elem.get_text(" "))
        if key and value:
            metadata[key.lower()] = value

    return metadata


def _find_event_container(anchor):
    """Find the closest block containing row metadata for a Vancouver event."""
    node = anchor
    while node is not None:
        if node.select_one(".phx.table-row-layout"):
            return node
        node = node.parent
    return None


def _extract_vancouver_listings(html_content: str, page_url: str) -> list[ProcurementListing]:
    soup = BeautifulSoup(html_content, "html.parser")

    listings: list[ProcurementListing] = []
    seen_ids: set[str] = set()

    for anchor in soup.select("a.btn-link-header[href]"):
        title = _normalize_text(anchor.get_text(" "))
        if not title:
            continue

        source_url = urljoin(page_url, anchor.get("href"))
        container = _find_event_container(anchor)
        metadata = _extract_metadata_map(container) if container else {}

        reference_number = metadata.get("number")
        category = metadata.get("type")
        close_date = _parse_vancouver_date(metadata.get("close"))
        open_date = _parse_vancouver_date(metadata.get("open"))

        source_listing_id = reference_number or source_url
        if source_listing_id in seen_ids:
            continue
        seen_ids.add(source_listing_id)

        description_parts = []
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
                source_listing_id=source_listing_id,
                status="Open",
                raw_location="Vancouver, British Columbia",
            )
        )

    return listings


async def vancouver_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape Vancouver's public bids page."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty Vancouver listing set")
        return []

    url = portal.url or VANCOUVER_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        html_content = await page.content()
        listings = _extract_vancouver_listings(html_content, page.url or url)
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
