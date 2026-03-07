"""
SEAO (Quebec) scraper.

Scrapes active tenders from the SEAO results page and paginates through all
available pages in the rendered HTML table.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.keywords import deduplicate_listings

try:
    from playwright.async_api import Locator, Page, async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    Locator = object  # type: ignore[assignment,misc]
    Page = object  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

SEAO_BASE_URL = "https://seao.gouv.qc.ca"
SEAO_RESULTS_URL = "https://seao.gouv.qc.ca/avis-resultat-recherche"
SEAO_ACTIVE_TENDERS_URL = (
    "https://seao.gouv.qc.ca/avis-resultat-recherche"
    "?statIds=6&tpIds=2%2C3%2C5%2C6%2C7%2C8%2C10%2C14%2C15%2C17%2C18%2C19"
)


def _normalize_header(value: str) -> str:
    """Normalize multilingual table header text for matching."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.strip().lower())


def _parse_date(value: str | None) -> str | None:
    """Parse SEAO display dates to ISO date format."""
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    # Keep only the date prefix if a time is included.
    raw = re.split(r"\s+", raw, maxsplit=1)[0] if re.match(r"\d{4}-\d{2}-\d{2}", raw) else raw

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    # Handle strings where date appears before time, ex: "2026-03-08 10:00".
    match = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if match:
        return match.group(1)

    match = re.search(r"(\d{2}/\d{2}/\d{4})", raw)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
        except ValueError:
            return None

    return None


def _header_index_map(headers: list[str]) -> dict[str, int]:
    """Map normalized SEAO table headers to known listing fields."""
    index: dict[str, int] = {}

    for i, raw_header in enumerate(headers):
        header = _normalize_header(raw_header)
        if not header:
            continue

        if "titre" in header or "title" in header:
            index.setdefault("title", i)
        elif (
            "reference" in header
            or "numero" in header
            or "num" in header
            or "no." in header
        ):
            index.setdefault("reference_number", i)
        elif "organisme" in header or "organisation" in header or "organization" in header:
            index.setdefault("organization", i)
        elif "categorie" in header or "category" in header:
            index.setdefault("category", i)
        elif "ouverture" in header or "publication" in header or "opening" in header:
            index.setdefault("open_date", i)
        elif "fermeture" in header or "limite" in header or "closing" in header:
            index.setdefault("close_date", i)

    return index


async def _extract_current_page_rows(page: Page) -> tuple[list[str], list[dict]]:
    """
    Extract header/cell data from the first populated table on the page.

    Returns:
        (headers, rows)
        rows format: [{"cells": [...], "href": str|None, "anchor_text": str|None}]
    """
    data = await page.evaluate(
        """
        () => {
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const tables = Array.from(document.querySelectorAll('table'));

          for (const table of tables) {
            const headers = Array.from(table.querySelectorAll('thead th')).map((th) => clean(th.innerText));
            const rows = Array.from(table.querySelectorAll('tbody tr'))
              .map((tr) => {
                const cells = Array.from(tr.querySelectorAll('td')).map((td) => clean(td.innerText));
                const link = tr.querySelector('a[href]');
                return {
                  cells,
                  href: link ? link.getAttribute('href') : null,
                  anchor_text: link ? clean(link.innerText) : null,
                };
              })
              .filter((row) => row.cells.length > 0 && row.cells.some((value) => value));

            if (rows.length === 0) {
              continue;
            }

            const hasConsulterLink = rows.some(
              (row) => row.href && row.href.includes('avis-resultat-recherche/consulter')
            );

            if (hasConsulterLink || headers.length >= 4) {
              return { headers, rows };
            }
          }

          return { headers: [], rows: [] };
        }
        """
    )

    headers = data.get("headers") or []
    rows = data.get("rows") or []
    return headers, rows


def _build_listing_from_row(
    headers: list[str],
    row: dict,
    page_url: str,
) -> ProcurementListing | None:
    """Map one SEAO table row into ProcurementListing."""
    cells = row.get("cells") or []
    if not cells:
        return None

    idx = _header_index_map(headers)

    def cell_value(key: str, fallback_index: int | None = None) -> str | None:
        i = idx.get(key, fallback_index)
        if i is None:
            return None
        if i < 0 or i >= len(cells):
            return None
        value = str(cells[i]).strip()
        return value or None

    title = (row.get("anchor_text") or cell_value("title", 0) or "").strip()
    if not title:
        return None

    reference_number = cell_value("reference_number", 1)
    organization = cell_value("organization", 2)
    category = cell_value("category", 3)
    open_date = _parse_date(cell_value("open_date", 4))
    close_date = _parse_date(cell_value("close_date", 5))

    detail_href = row.get("href")
    detail_url = urljoin(page_url, detail_href) if detail_href else None

    description_parts = []
    if organization:
        description_parts.append(f"Organization: {organization}")
    if category:
        description_parts.append(f"Category: {category}")

    return ProcurementListing(
        title=title,
        reference_number=reference_number,
        description=" | ".join(description_parts) if description_parts else None,
        posting_date=open_date,
        closing_date=close_date,
        source_url=detail_url,
        source_listing_id=reference_number or detail_url,
        status="Open",
        raw_location=organization,
    )


async def _locator_disabled(locator: Locator) -> bool:
    """Return True when locator appears disabled."""
    try:
        disabled_attr = await locator.get_attribute("disabled")
        aria_disabled = await locator.get_attribute("aria-disabled")
        class_name = (await locator.get_attribute("class") or "").lower()
    except Exception:
        return True

    return (
        disabled_attr is not None
        or aria_disabled == "true"
        or "disabled" in class_name
    )


async def _go_to_next_page(page: Page) -> bool:
    """Click next page control when available and enabled."""
    next_selectors = [
        "a[rel='next']",
        "button[aria-label*='Next']",
        "button[aria-label*='Suivant']",
        "a[aria-label*='Next']",
        "a[aria-label*='Suivant']",
        "button:has-text('Next')",
        "button:has-text('Suivant')",
        "a:has-text('Next')",
        "a:has-text('Suivant')",
        "li.next:not(.disabled) a",
    ]

    for selector in next_selectors:
        locator = page.locator(selector)
        count = await locator.count()
        if count == 0:
            continue

        for i in range(count):
            candidate = locator.nth(i)
            try:
                if not await candidate.is_visible(timeout=500):
                    continue
            except Exception:
                continue

            if await _locator_disabled(candidate):
                continue

            try:
                await candidate.click(timeout=3000)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2500)
                return True
            except Exception:
                continue

    return False


async def seao_scrape(
    portal: PortalRecord,
    keywords_by_category: dict[str, dict[str, list[str]]] | None = None,
) -> list[ProcurementListing]:
    """
    Scrape active tenders from SEAO paginated results.

    Args:
        portal: The portal record (used for logging/consistency).
        keywords_by_category: Unused; kept for signature compatibility.

    Returns:
        List of ProcurementListing objects.
    """
    del keywords_by_category  # Signature compatibility.

    if async_playwright is None:
        logger.error(
            "playwright not installed. SEAO scraping requires playwright package."
        )
        return []

    browser = None
    p = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        await page.goto(SEAO_ACTIVE_TENDERS_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        logger.info("Starting SEAO scrape for '%s'", portal.name)

        listings: list[ProcurementListing] = []
        seen_listing_ids: set[str] = set()
        seen_page_signatures: set[tuple[str, ...]] = set()

        max_pages = 100
        for _ in range(max_pages):
            headers, rows = await _extract_current_page_rows(page)

            if not rows:
                logger.info("SEAO: no rows detected on current page, stopping pagination")
                break

            page_ids: list[str] = []
            for row in rows:
                listing = _build_listing_from_row(headers, row, page.url)
                if listing is None:
                    continue

                fingerprint = (
                    listing.source_listing_id
                    or listing.source_url
                    or listing.title
                )
                if fingerprint in seen_listing_ids:
                    continue

                seen_listing_ids.add(fingerprint)
                page_ids.append(fingerprint)
                listings.append(listing)

            page_signature = tuple(sorted(page_ids))
            if page_signature in seen_page_signatures:
                logger.info("SEAO: repeated page signature detected, stopping pagination")
                break
            seen_page_signatures.add(page_signature)

            moved = await _go_to_next_page(page)
            if not moved:
                break

        listings = deduplicate_listings(listings)

        logger.info(
            "SEAO scrape complete for '%s': %d listings found",
            portal.name,
            len(listings),
        )
        return listings

    except Exception:
        logger.exception("SEAO scrape failed for portal '%s'", portal.name)
        return []

    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.warning("Failed to close browser for SEAO portal '%s'", portal.name)
        if p is not None:
            try:
                await p.stop()
            except Exception:
                pass
