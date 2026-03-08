"""New Brunswick Opportunities Network (NBON) scraper."""

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

NBON_URL = "https://nbon-rpanb.gnb.ca/"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _parse_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    text = re.sub(r"\s+[A-Z]{2,4}$", "", text)

    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


async def _extract_rows_from_frame(frame) -> list[dict]:
    return await frame.evaluate(
        r"""
        () => {
          const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
          const rows = [];

          const tables = Array.from(document.querySelectorAll('table'));
          for (const table of tables) {
            const headers = Array.from(table.querySelectorAll('thead th')).map((th) => clean(th.innerText).toLowerCase());
            const bodyRows = Array.from(table.querySelectorAll('tbody tr'));
            for (const tr of bodyRows) {
              const cells = Array.from(tr.querySelectorAll('td')).map((td) => clean(td.innerText));
              if (!cells.length || cells.every((c) => !c)) continue;
              const row = {};
              headers.forEach((h, i) => { if (h && cells[i]) row[h] = cells[i]; });
              const link = tr.querySelector('a[href]');
              if (link) row.href = link.getAttribute('href');
              if (!row.title && cells[0]) row.title = cells[0];
              rows.push(row);
            }
          }

          if (!rows.length) {
            const links = Array.from(document.querySelectorAll('a[href]'));
            for (const link of links) {
              const text = clean(link.innerText);
              if (!text) continue;
              if (/tender|opportunit|bid|solicitation|appel d'offres/i.test(text)) {
                rows.push({ title: text, href: link.getAttribute('href') });
              }
            }
          }

          return rows;
        }
        """
    )


def _rows_to_listings(rows: list[dict], base_url: str) -> list[ProcurementListing]:
    listings: list[ProcurementListing] = []

    for row in rows:
        title = _normalize_text(row.get("title") or row.get("opportunity") or row.get("solicitation"))
        if not title:
            continue

        reference_number = _normalize_text(row.get("reference") or row.get("reference number") or row.get("id"))
        category = _normalize_text(row.get("category") or row.get("type"))
        closing_date = _parse_date(row.get("closing date") or row.get("close date") or row.get("close"))

        href = _normalize_text(row.get("href") or row.get("source_url"))
        source_url = urljoin(base_url, href) if href else base_url

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=reference_number,
                description=f"Category: {category}" if category else None,
                posting_date=_parse_date(row.get("posting date") or row.get("open date")),
                closing_date=closing_date,
                source_url=source_url,
                source_listing_id=reference_number or source_url,
                status="Open",
                raw_location="New Brunswick",
            )
        )

    return listings


async def nbon_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape NBON public opportunities from main page or loaded iframe content."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty NBON listing set")
        return []

    url = portal.url or NBON_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(5000)

        rows: list[dict] = []

        # Prefer iframe content when NBON loads the app there.
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            frame_url = frame.url or ""
            if frame_url and frame_url != "about:blank":
                try:
                    extracted = await _extract_rows_from_frame(frame)
                    if extracted:
                        rows.extend(extracted)
                except Exception:
                    logger.debug("Skipping NBON frame parse failure for URL %s", frame_url)

        if not rows:
            rows = await _extract_rows_from_frame(page.main_frame)

        listings = _rows_to_listings(rows or [], page.url or url)
        listings = deduplicate_listings(listings)

        logger.info("Portal '%s': NBON scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': NBON scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
