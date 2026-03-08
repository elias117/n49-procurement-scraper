"""City of Montreal tenders scraper."""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime
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

MONTREAL_LISTING_URL = "https://montreal.ca/avis-dappel-doffres"

_FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "fevr": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_montreal_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    plain = _strip_accents(text).lower()

    # French long form dates (e.g., "Mardi 7 avril 2026 avant 14 h 00").
    match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", plain)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        month = _FRENCH_MONTHS.get(month_name)
        if month is not None:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _extract_reference_from_url_or_title(source_url: str, title: str) -> str | None:
    # Prefer explicit tender number patterns in title.
    match = re.search(r"\b\d{4}-\d{2,}[A-Z]?\b", title)
    if match:
        return match.group(0)

    # Fallback: numeric token at end of URL slug.
    match = re.search(r"-(\d{5,})(?:$|[/?#])", source_url)
    if match:
        return match.group(1)

    return None


def _extract_summary_listings(html_content: str, page_url: str) -> tuple[list[ProcurementListing], str | None]:
    soup = BeautifulSoup(html_content, "html.parser")

    summaries: list[ProcurementListing] = []
    for item in soup.select("li.list-group-item.list-element"):
        link = item.select_one("a[href]")
        title_elem = item.select_one(".list-group-item-title")

        title = _normalize_text(title_elem.get_text(" ") if title_elem else None)
        href = _normalize_text(link.get("href") if link else None)

        if not title or not href:
            continue

        source_url = urljoin(page_url, href)

        info_items = [_normalize_text(info.get_text(" ")) for info in item.select(".list-group-info-item")]
        info_items = [value for value in info_items if value]

        posting_date = _parse_montreal_date(info_items[0]) if info_items else None
        raw_location = info_items[1] if len(info_items) > 1 else None

        reference = _extract_reference_from_url_or_title(source_url, title)

        summaries.append(
            ProcurementListing(
                title=title,
                reference_number=reference,
                description=None,
                posting_date=posting_date,
                closing_date=None,
                source_url=source_url,
                source_listing_id=reference or source_url,
                status="Open",
                raw_location=raw_location,
            )
        )

    next_link = soup.select_one("a[aria-label*='Suivant'][href]")
    next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None

    return summaries, next_url


def _extract_detail_metadata(html_content: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html_content, "html.parser")

    metadata: dict[str, str | None] = {
        "category": None,
        "reference_number": None,
        "closing_date": None,
        "posting_date": None,
    }

    closing_label = soup.find(class_="list-item-icon-label", string=re.compile(r"Date limite", re.IGNORECASE))
    if closing_label:
        parent = closing_label.parent
        if parent:
            text = _normalize_text(parent.get_text(" "))
            if text:
                text = text.replace(_normalize_text(closing_label.get_text(" ")) or "", "").strip(" :")
                metadata["closing_date"] = _parse_montreal_date(text)

    for row in soup.select(".list-item"):
        label_elem = row.select_one(".list-item-label")
        if not label_elem:
            continue

        label = _strip_accents(_normalize_text(label_elem.get_text(" ")) or "").lower()

        value_elem = row.select_one(".list-item-content")
        raw_value = _normalize_text(value_elem.get_text(" ") if value_elem else row.get_text(" "))
        if not raw_value:
            continue

        label_text = _normalize_text(label_elem.get_text(" ")) or ""
        value = raw_value.replace(label_text, "", 1).strip(" :")

        if "categorie" in label:
            metadata["category"] = value or metadata["category"]
        elif "numero d'appel d'offres" in label or "numero" in label:
            metadata["reference_number"] = value or metadata["reference_number"]
        elif "date de disponibilite" in label:
            parsed = _parse_montreal_date(value)
            if parsed:
                metadata["posting_date"] = parsed

    return metadata


def _merge_summary_and_detail(
    summary: ProcurementListing,
    detail_metadata: dict[str, str | None],
) -> ProcurementListing:
    reference_number = detail_metadata.get("reference_number") or summary.reference_number
    category = detail_metadata.get("category")

    description = summary.description
    if category:
        description = f"Category: {category}" if not description else f"{description} | Category: {category}"

    source_listing_id = reference_number or summary.source_listing_id or summary.source_url

    return ProcurementListing(
        title=summary.title,
        reference_number=reference_number,
        description=description,
        posting_date=detail_metadata.get("posting_date") or summary.posting_date,
        closing_date=detail_metadata.get("closing_date") or summary.closing_date,
        source_url=summary.source_url,
        source_listing_id=source_listing_id,
        status=summary.status,
        raw_location=summary.raw_location,
    )


async def montreal_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Scrape Montreal call-for-tender listings with detail-page enrichment."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty Montreal listing set")
        return []

    start_url = portal.url
    if "avis-dappel" not in start_url and "avis-dappels" not in start_url:
        start_url = MONTREAL_LISTING_URL

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        all_summaries: list[ProcurementListing] = []
        next_url: str | None = start_url
        visited_pages: set[str] = set()
        max_pages = 25

        while next_url and next_url not in visited_pages and len(visited_pages) < max_pages:
            visited_pages.add(next_url)
            await page.goto(next_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(1500)

            html_content = await page.content()
            summaries, discovered_next = _extract_summary_listings(html_content, page.url or next_url)
            all_summaries.extend(summaries)
            next_url = discovered_next

        logger.info(
            "Portal '%s': Montreal summary pages=%d listings=%d",
            portal.name,
            len(visited_pages),
            len(all_summaries),
        )

        enriched: list[ProcurementListing] = []
        for summary in all_summaries:
            if not summary.source_url:
                enriched.append(summary)
                continue

            try:
                await page.goto(summary.source_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(1000)
                detail_html = await page.content()
                detail_metadata = _extract_detail_metadata(detail_html)
                enriched.append(_merge_summary_and_detail(summary, detail_metadata))
            except Exception:
                logger.exception(
                    "Portal '%s': failed Montreal detail enrichment for %s",
                    portal.name,
                    summary.source_url,
                )
                enriched.append(summary)

        listings = deduplicate_listings(enriched)
        logger.info("Portal '%s': Montreal scraped %d listings", portal.name, len(listings))
        return listings

    except Exception:
        logger.exception("Portal '%s': Montreal scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
