"""New Brunswick Opportunities Network (NBON) scraper."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.keywords import deduplicate_listings

try:
    from playwright.async_api import Frame, Page, async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    Frame = object  # type: ignore[assignment,misc]
    Page = object  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

NBON_URL = "https://nbon-rpanb.gnb.ca/"
NBON_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


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
        "%Y/%m/%d %H:%M",
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


def _extract_display_url(href: str | None, frame_url: str) -> str | None:
    """Extract a usable NBON detail URL from JavaScript openWindow() href values."""
    text = _normalize_text(href)
    if not text:
        return None

    match = re.search(r"openWindow\('([^']*showDisplayDocument[^']*)'", text)
    if match:
        return urljoin(frame_url, match.group(1))

    if "showDisplayDocument" in text:
        return urljoin(frame_url, text)

    if text.startswith(("http://", "https://")):
        return text

    return urljoin(frame_url, text)


def _to_listing(row: dict, frame_url: str) -> ProcurementListing | None:
    reference_number = _normalize_text(row.get("reference_number"))
    title = _normalize_text(row.get("title")) or reference_number
    if not title:
        return None

    source_url = _extract_display_url(row.get("href"), frame_url) or frame_url
    organization = _normalize_text(row.get("organization"))

    return ProcurementListing(
        title=title,
        reference_number=reference_number,
        description=f"Organization: {organization}" if organization else None,
        posting_date=_parse_date(_normalize_text(row.get("posting_date"))),
        closing_date=_parse_date(_normalize_text(row.get("closing_date"))),
        source_url=source_url,
        source_listing_id=reference_number or source_url,
        status="Open",
        raw_location="New Brunswick",
    )


async def _ensure_nbon_home(page: Page, start_url: str) -> None:
    await page.goto(start_url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(4000)

    body_text = _normalize_text(await page.text_content("body")) or ""
    page_url = page.url or ""
    if "page not found" in body_text.lower() or "www2.gnb.ca" in page_url:
        await page.goto(NBON_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(4000)


async def _open_opportunity_frame(page: Page) -> Frame | None:
    # First, click "Browse Tenders and Awards" from the welcome content frame.
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        if "showWelcomeContent" not in (frame.url or ""):
            continue
        link = frame.locator("a:has-text('Browse Tenders and Awards')").first
        if await link.count():
            await link.click()
            await page.wait_for_timeout(4000)
            break

    browse_menu = page.locator("#menu_ExtBrowseOpportunities").first
    if await browse_menu.count():
        await browse_menu.click()
        await page.wait_for_timeout(4000)

    content_frames = [frame for frame in page.frames if frame != page.main_frame]
    if not content_frames:
        return None

    content_frame = content_frames[-1]
    all_open = content_frame.locator("a:has-text('All Open Opportunities')").first
    if await all_open.count():
        await all_open.click()
        await page.wait_for_timeout(5000)
        content_frames = [frame for frame in page.frames if frame != page.main_frame]
        if content_frames:
            return content_frames[-1]

    return content_frame


async def _extract_open_rows(frame: Frame) -> list[dict]:
    return await frame.evaluate(
        r"""
        () => {
          const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
          const tableRows = Array.from(document.querySelectorAll('table tr'));
          const rows = [];

          for (let idx = 0; idx < tableRows.length; idx += 1) {
            const row = tableRows[idx];
            const cells = Array.from(row.querySelectorAll('td')).map((td) => clean(td.innerText));
            if (cells.length < 5) continue;
            if (!/^\d+$/.test(cells[0] || '')) continue;
            if (!/\d{4}\/\d{2}\/\d{2}/.test(cells[3] || '')) continue;

            const detailRow = tableRows[idx + 1];
            const detailCells = detailRow
              ? Array.from(detailRow.querySelectorAll('td')).map((td) => clean(td.innerText))
              : [];
            let title = clean(detailCells[2] || detailCells[1] || '');
            if (!title || /advertisement/i.test(title)) {
              title = cells[1];
            }

            const link = row.querySelector("a[href*='showDisplayDocument']");
            rows.push({
              title,
              reference_number: cells[1] || null,
              organization: cells[2] || null,
              posting_date: cells[3] || null,
              closing_date: cells[4] || null,
              href: link ? link.getAttribute('href') : null,
            });
          }

          return rows;
        }
        """
    )


async def nbon_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape NBON open opportunities through the public anonymous workflow."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty NBON listing set")
        return []

    start_url = portal.url or NBON_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=NBON_USER_AGENT,
        )
        page = await context.new_page()

        await _ensure_nbon_home(page, start_url)
        frame = await _open_opportunity_frame(page)
        if frame is None:
            logger.warning("Portal '%s': NBON content frame not found", portal.name)
            return []

        rows = await _extract_open_rows(frame)
        frame_url = frame.url or page.url or NBON_URL
        listings = [
            listing
            for row in rows
            if (listing := _to_listing(row, frame_url)) is not None
        ]
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
