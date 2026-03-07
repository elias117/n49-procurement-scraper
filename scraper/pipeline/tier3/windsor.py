"""City of Windsor open data tender scraper."""

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

WINDSOR_LISTING_URL = "https://opendata.citywindsor.ca/Tools/BidsAndTenders"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _parse_windsor_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    # Example: Mar 04, 2026 12:00 AM EST
    text = re.sub(r"\s+[A-Z]{2,4}$", "", text)

    for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _extract_label_date(row, label: str) -> str | None:
    strong = row.find("strong", string=re.compile(rf"^{re.escape(label)}\s*$", re.IGNORECASE))
    if not strong:
        return None

    span = strong.find_next("span")
    if not span:
        return None

    return _parse_windsor_date(span.get_text(" ", strip=True))


def _extract_category(row) -> str | None:
    classes = set(row.get("class") or [])
    category_map = {
        "Construction": "Construction",
        "Consulting": "Consulting",
        "GeneralServices": "General Services",
        "Goods": "Goods",
    }

    for class_name, category in category_map.items():
        if class_name in classes:
            return category

    return None


def _extract_row_source_url(row, page_url: str) -> str:
    detail_link = row.select_one(".BT_TenderDetails a[href]")
    if detail_link and detail_link.get("href"):
        return urljoin(page_url, detail_link["href"])
    return page_url


def _extract_row_source_id(source_url: str, title: str, closing_date: str | None) -> str:
    match = re.search(r"\{([A-Fa-f0-9\-]{10,})\}", source_url)
    if match:
        return match.group(1)
    return f"{title}|{closing_date or ''}"


def _extract_windsor_listings(html_content: str, page_url: str) -> list[ProcurementListing]:
    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.select("tbody#tableBody tr.BT_BidAndTender")

    listings: list[ProcurementListing] = []
    for row in rows:
        title_elem = row.select_one("span.h5")
        title = _normalize_text(title_elem.get_text(" ") if title_elem else None)
        if not title:
            continue

        category = _extract_category(row)
        open_date = _extract_label_date(row, "Open:")
        close_date = _extract_label_date(row, "Close:")
        source_url = _extract_row_source_url(row, page_url)

        status = "Closed" if "HasUnofficialResults" in (row.get("class") or []) else "Open"

        info_text = _normalize_text(
            row.select_one(".BT_BidAndTenderInfo").get_text(" ")
            if row.select_one(".BT_BidAndTenderInfo")
            else None
        )
        description_parts = []
        if category:
            description_parts.append(f"Category: {category}")
        if info_text:
            description_parts.append(info_text)
        description = " | ".join(description_parts) if description_parts else None

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=None,
                description=description,
                posting_date=open_date,
                closing_date=close_date,
                source_url=source_url,
                source_listing_id=_extract_row_source_id(source_url, title, close_date),
                status=status,
                raw_location="Windsor, Ontario",
            )
        )

    return listings


async def windsor_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape Windsor DataTables DOM-loaded bid listings."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty Windsor listing set")
        return []

    url = portal.url or WINDSOR_LISTING_URL
    if "opendata.citywindsor.ca" not in url:
        url = WINDSOR_LISTING_URL

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
        listings = _extract_windsor_listings(html_content, page.url or url)
        listings = deduplicate_listings(listings)

        logger.info("Portal '%s': Windsor scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': Windsor scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
