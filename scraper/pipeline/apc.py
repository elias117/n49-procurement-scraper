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

        reference_number = _normalize_text(row.get("reference_number") or row.get("reference"))
        category = _normalize_text(row.get("category") or row.get("type"))
        closing_date = _parse_date(row.get("closing_date") or row.get("close_date") or row.get("close"))

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
                raw_location="Alberta",
            )
        )

    return listings


async def apc_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape APC public listings from rendered DOM content."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty APC listing set")
        return []

    url = portal.url or APC_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(6000)

        rows = await page.evaluate(
            r"""
            () => {
              const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
              const results = [];

              // Table-style listings
              const tables = Array.from(document.querySelectorAll('table'));
              for (const table of tables) {
                const headers = Array.from(table.querySelectorAll('thead th')).map((th) => clean(th.innerText).toLowerCase());
                for (const tr of Array.from(table.querySelectorAll('tbody tr'))) {
                  const cells = Array.from(tr.querySelectorAll('td')).map((td) => clean(td.innerText));
                  if (!cells.length || cells.every((c) => !c)) continue;
                  const row = {};
                  headers.forEach((h, i) => { if (h && cells[i]) row[h] = cells[i]; });
                  const link = tr.querySelector('a[href]');
                  if (link) row.href = link.getAttribute('href');
                  if (!row.title && cells[0]) row.title = cells[0];
                  results.push(row);
                }
              }

              // Card-style listings fallback
              if (!results.length) {
                const cards = Array.from(document.querySelectorAll('article, .card, [class*="opportun"], [class*="tender"]'));
                for (const card of cards) {
                  const titleNode = card.querySelector('h1, h2, h3, h4, a');
                  const title = clean(titleNode && titleNode.innerText);
                  if (!title) continue;
                  const link = card.querySelector('a[href]');
                  results.push({
                    title,
                    href: link ? link.getAttribute('href') : null,
                    close: clean(card.innerText.match(/(Close|Closing|Due)[:\s]+[^\n]+/i)?.[0] || ''),
                  });
                }
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
