"""Alberta Purchasing Connection (APC) scraper."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.keywords import deduplicate_listings

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

APC_URL = "https://vendor.purchasingconnection.ca/"
APC_SEARCH_URL = "https://purchasing.alberta.ca/search?npo=1"
APC_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _parse_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    # Keep only the date token for values like "Mar 15, 2026 • 2:09 pm (MT)".
    match = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", text)
    if match:
        text = match.group(1)

    text = re.sub(r"\s+[A-Z]{2,4}$", "", text)

    for fmt in (
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d/%m/%Y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)

    return None


def _rows_to_listings(rows: list[dict], base_url: str) -> list[ProcurementListing]:
    listings: list[ProcurementListing] = []

    for row in rows:
        title = _normalize_text(row.get("title"))
        if not title:
            continue

        reference_number = _normalize_text(
            row.get("reference_number") or row.get("reference")
        )
        category = _normalize_text(row.get("category") or row.get("type"))
        closing_date = _parse_date(
            row.get("closing_date") or row.get("close_date") or row.get("close")
        )
        raw_location = _normalize_text(
            row.get("region")
            or row.get("location")
            or row.get("raw_location")
        )

        href = _normalize_text(row.get("source_url") or row.get("href"))
        source_url = urljoin(base_url, href) if href else base_url

        description = f"Category: {category}" if category else None

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=reference_number,
                description=description,
                posting_date=_parse_date(row.get("posting_date") or row.get("open_date") or row.get("open")),
                closing_date=closing_date,
                source_url=source_url,
                source_listing_id=reference_number or source_url,
                status="Open",
                raw_location=raw_location or "Alberta",
            )
        )

    return listings


def _normalize_apc_listing_url(portal_url: str) -> str:
    base = (portal_url or "").strip()
    if not base:
        return APC_SEARCH_URL

    lowered = base.lower()
    if "/search" in lowered:
        if "?" in base:
            return base
        return f"{base}?npo=1"

    return APC_SEARCH_URL


async def apc_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape APC public listings from rendered DOM content."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty APC listing set")
        return []

    url = _normalize_apc_listing_url(portal.url or APC_URL)

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=APC_USER_AGENT,
        )
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)

        if "/search" not in (page.url or ""):
            await page.goto(APC_SEARCH_URL, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(8000)

        rows = await page.evaluate(
            r"""
            () => {
              const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
              const results = [];

              const cards = Array.from(document.querySelectorAll('apc-opportunity-search-result'));
              for (const card of cards) {
                const titleLink = card.querySelector("a[href*='/posting/']");
                const title = clean(titleLink && titleLink.innerText);
                if (!title) continue;

                const row = {
                  title,
                  href: titleLink ? titleLink.getAttribute('href') : null,
                };

                for (const detail of Array.from(card.querySelectorAll('.search-result__detail'))) {
                  const text = clean(detail.innerText);
                  if (!text) continue;

                  if (/^APC Reference/i.test(text)) {
                    row.reference_number = clean(text.replace(/^APC Reference\s*#?\s*/i, ''));
                  } else if (/^Category/i.test(text)) {
                    row.category = clean(text.replace(/^Category\s*/i, ''));
                  } else if (/^Posting Date/i.test(text)) {
                    row.posting_date = clean(text.replace(/^Posting Date\s*•?\s*Time\s*/i, ''));
                  } else if (/^Closing Date/i.test(text)) {
                    row.closing_date = clean(text.replace(/^Closing Date\s*•?\s*Time\s*/i, ''));
                  } else if (/^Region\(s\) of Delivery/i.test(text)) {
                    row.region = clean(text.replace(/^Region\(s\) of Delivery\s*/i, ''));
                  }
                }

                results.push(row);
              }

              return results;
            }
            """
        )

        listings = _rows_to_listings(rows or [], page.url or url)
        listings = deduplicate_listings(listings)

        logger.info("Portal '%s': APC scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': APC scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
