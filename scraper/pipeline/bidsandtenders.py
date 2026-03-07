"""
BidsAndTenders platform scraper.

Scrapes BidsAndTenders portals directly from the standard listing URL:
{base_url}/Module/Tenders/en

Uses Playwright to load the listing page, then pulls all active/open tenders
via the same paginated data source used by the portal UI. No keyword search is
performed.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import NamedTuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.extraction import extract_listing_detail, extract_listings_from_html
from scraper.pipeline.keywords import deduplicate_listings

try:
    from playwright.async_api import BrowserContext, Page, async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    BrowserContext = object  # type: ignore[assignment,misc]
    Page = object  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class BidsAndTendersResult(NamedTuple):
    """Result from a BidsAndTenders scrape."""

    listings: list[ProcurementListing]
    search_used: bool  # Always False: direct full listing scrape.


_BT_DATE_RE = re.compile(r"/Date\((\d+)\)/")


def _is_sparse(listing: ProcurementListing) -> bool:
    """
    Check if a listing is sparse (missing key detail-page fields).

    A listing is considered sparse if:
    - It has no description at all, OR
    - Its description is very short (<50 chars -- likely a fragment from the
      summary page, not the full detail), OR
    - It has a description but is missing BOTH closing_date and contact
      information (fields typically found on detail pages).

    BidsAndTenders listing pages show a table with title and maybe closing
    date but rarely descriptions, contact info, or dollar values.
    """
    if listing.description is None:
        return True
    if len(listing.description) < 50:
        return True
    if listing.closing_date is None and listing.contact_name is None:
        return True
    return False


def _resolve_url(source_url: str, portal_url: str) -> str:
    """
    Resolve a potentially relative URL against the portal base URL.

    Args:
        source_url: The URL from the listing (may be relative).
        portal_url: The portal's base URL for resolving relative paths.

    Returns:
        An absolute URL string.
    """
    if source_url.startswith(("http://", "https://")):
        return source_url
    return urljoin(portal_url, source_url)


def _normalize_url(value) -> str | None:
    """Normalize an extracted URL-like value to a non-empty string."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _fix_source_urls(
    listings: list[ProcurementListing],
    page_url: str,
    portal_url: str,
) -> list[ProcurementListing]:
    """
    Resolve relative listing URLs and replace cross-domain links with page URL.
    """
    portal_domain = urlparse(portal_url).netloc.lower()
    fallback_url = _normalize_url(page_url) or portal_url

    for listing in listings:
        source_url = _normalize_url(listing.source_url)
        if not source_url:
            listing.source_url = fallback_url
            continue

        resolved_url = _resolve_url(source_url, portal_url)
        listing_domain = urlparse(resolved_url).netloc.lower()
        if listing_domain and listing_domain != portal_domain:
            listing.source_url = fallback_url
        else:
            listing.source_url = resolved_url

    return listings


def _merge_detail(
    original: ProcurementListing, detail: ProcurementListing
) -> ProcurementListing:
    """
    Merge detail page data into an original sparse listing.

    For each field, uses the detail page value if the original is None.
    The original title is always preserved (it came from the listing page).

    Args:
        original: The sparse listing from the listing page.
        detail: The full listing extracted from the detail page.

    Returns:
        A new ProcurementListing with merged fields.
    """
    merged_data = {}
    for field_name in ProcurementListing.model_fields:
        orig_val = getattr(original, field_name)
        detail_val = getattr(detail, field_name)
        if field_name == "title":
            merged_data[field_name] = orig_val
        elif orig_val is None and detail_val is not None:
            merged_data[field_name] = detail_val
        else:
            merged_data[field_name] = orig_val
    return ProcurementListing(**merged_data)


async def _enrich_with_details(
    listings: list[ProcurementListing],
    page: Page,
    portal: PortalRecord,
) -> list[ProcurementListing]:
    """
    Enrich sparse listings by visiting their detail pages using Playwright.

    For each listing that has a source_url and is sparse (missing description),
    navigates to the detail page, extracts full details, and merges them back
    into the listing.

    Respects config.BROWSER_DETAIL_MAX_PAGES to limit the number of detail
    page visits per scrape run.

    Args:
        listings: List of ProcurementListing objects from the listing page.
        page: The Playwright page instance.
        portal: The portal record for URL resolution and naming.

    Returns:
        Updated list of ProcurementListing objects with enriched details.
    """
    sparse_listings = [
        (i, listing)
        for i, listing in enumerate(listings)
        if listing.source_url and _is_sparse(listing)
    ]

    if not sparse_listings:
        logger.info(
            "Portal '%s': no sparse listings with URLs to enrich",
            portal.name,
        )
        return listings

    max_pages = config.BROWSER_DETAIL_MAX_PAGES
    to_enrich = sparse_listings[:max_pages]

    logger.info(
        "Portal '%s': enriching %d/%d sparse listings (max %d)",
        portal.name,
        len(to_enrich),
        len(sparse_listings),
        max_pages,
    )

    enriched = list(listings)  # shallow copy

    for idx, (orig_index, listing) in enumerate(to_enrich):
        detail_url = _resolve_url(listing.source_url, portal.url)

        try:
            await page.goto(detail_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            html_content = await page.content()

            detail = extract_listing_detail(html_content, portal.name)

            if detail is not None:
                enriched[orig_index] = _merge_detail(listing, detail)
                logger.info(
                    "Portal '%s': enriched listing '%s' from detail page (%d/%d)",
                    portal.name,
                    listing.title,
                    idx + 1,
                    len(to_enrich),
                )
            else:
                logger.warning(
                    "Portal '%s': detail extraction returned None for '%s'",
                    portal.name,
                    listing.title,
                )
        except Exception:
            logger.exception(
                "Portal '%s': failed to enrich listing '%s' from %s",
                portal.name,
                listing.title,
                detail_url,
            )

    return enriched


def _parse_bt_date(value: object) -> str | None:
    """
    Parse a BidsAndTenders date value to ISO date (YYYY-MM-DD).

    Supports:
    - /Date(1773252000000)/
    - ISO date/time strings
    - Common date display formats from listing pages
    """
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    match = _BT_DATE_RE.search(raw)
    if match:
        try:
            dt = datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
            return dt.date().isoformat()
        except Exception:
            return None

    # Trim timezone suffixes in parentheses from display strings.
    raw = re.sub(r"\s*\([^)]*\)$", "", raw)

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%b %d, %Y",
        "%B %d, %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    # Handle strings like "Mar 10, 2026 2:00 PM".
    for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _html_to_text(value: object) -> str | None:
    """Convert HTML snippets to clean plain text."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text or None


async def _extract_search_metadata(page: Page) -> tuple[str, str, str] | None:
    """
    Extract hidden values required for BidsAndTenders search endpoint calls.

    Returns (home_path, node_id, anti_forgery_token) or None if unavailable.
    """
    try:
        home_path = await page.locator("#Home").input_value()
        node_id = await page.locator("#NodeId").input_value()
        token = await page.locator(
            "#bidDetailAntiForgery input[name='__RequestVerificationToken']"
        ).input_value()
    except Exception:
        logger.warning("Failed to read BidsAndTenders listing metadata from page")
        return None

    home_path = (home_path or "").strip()
    node_id = (node_id or "").strip()
    token = (token or "").strip()

    if not home_path or not node_id or not token:
        return None

    return home_path, node_id, token


async def _fetch_open_tenders(
    context: BrowserContext,
    listing_url: str,
    base_url: str,
    home_path: str,
    node_id: str,
    token: str,
    page_size: int = 100,
    max_pages: int = 100,
) -> list[dict]:
    """
    Fetch all open tenders from the BidsAndTenders JSON endpoint.

    This endpoint backs the listing page repeater and supports pagination.
    """
    endpoint = f"{base_url}{home_path}/Tender/Search/{node_id}"
    all_rows: list[dict] = []
    start = 0
    total_items: int | None = None

    for _ in range(max_pages):
        params = {
            "status": "Open",
            "limit": str(page_size),
            "start": str(start),
            "dir": "ASC",
            "from": "",
            "to": "",
            "sort": "DateClosing ASC,Id",
        }

        response = await context.request.post(
            endpoint,
            params=params,
            headers={
                "Referer": listing_url,
                "X-Requested-With": "XMLHttpRequest",
            },
            form={
                "keywords": "",
                "__RequestVerificationToken": token,
            },
            timeout=30000,
        )

        if not response.ok:
            logger.warning(
                "BidsAndTenders endpoint request failed: %s status=%s",
                endpoint,
                response.status,
            )
            break

        try:
            payload = await response.json()
        except Exception:
            logger.exception(
                "Failed parsing BidsAndTenders JSON payload from %s",
                endpoint,
            )
            break

        if not payload.get("success"):
            logger.warning(
                "BidsAndTenders endpoint returned success=false for %s",
                endpoint,
            )
            break

        rows = payload.get("data") or []
        if not isinstance(rows, list):
            logger.warning("Unexpected BidsAndTenders payload shape for %s", endpoint)
            break

        if total_items is None:
            try:
                total_items = int(payload.get("total") or 0)
            except (TypeError, ValueError):
                total_items = 0

        all_rows.extend(rows)

        if not rows:
            break

        start += len(rows)

        if total_items and start >= total_items:
            break

        # Safety break if API does not return enough metadata.
        if len(rows) < page_size and (not total_items or len(all_rows) >= total_items):
            break

    return all_rows


def _row_to_listing(row: dict, base_url: str, home_path: str) -> ProcurementListing | None:
    """Map a BidsAndTenders search row dict into ProcurementListing."""
    title = str(row.get("Title") or "").strip()
    if not title:
        return None

    source_listing_id = str(row.get("Id") or "").strip() or None
    detail_url = None
    if source_listing_id:
        detail_url = urljoin(base_url, f"{home_path}/Tender/Detail/{source_listing_id}")

    return ProcurementListing(
        title=title,
        description=_html_to_text(row.get("Description")),
        source_url=detail_url,
        source_listing_id=source_listing_id,
        status=(str(row.get("Status")).strip() or None) if row.get("Status") else None,
        posting_date=_parse_bt_date(row.get("DateAvailable") or row.get("DateAvailableDisplay")),
        closing_date=_parse_bt_date(row.get("DateClosing") or row.get("DateClosingDisplay")),
    )


async def bidsandtenders_scrape(
    portal: PortalRecord,
    keywords_by_category: dict[str, dict[str, list[str]]] | None = None,
) -> BidsAndTendersResult:
    """
    Scrape all active/open listings from a BidsAndTenders portal.

    Keyword filtering/search is intentionally not used. This scraper pulls all
    open listings from the portal's standard listing datasource and paginates
    through all result pages.

    Args:
        portal: The portal record with URL and metadata.
        keywords_by_category: Unused (kept for backward-compatible signature).

    Returns:
        BidsAndTendersResult with listings and search_used=False.
    """
    del keywords_by_category  # Kept for backward compatibility; not used.

    if async_playwright is None:
        logger.error(
            "playwright not installed. "
            "BidsAndTenders scraping requires playwright package."
        )
        return BidsAndTendersResult(listings=[], search_used=False)

    parsed = urlparse(portal.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    listing_url = f"{base_url}/Module/Tenders/en"

    logger.info(
        "Starting BidsAndTenders direct listing scrape for '%s' at %s",
        portal.name,
        listing_url,
    )

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

        await page.goto(listing_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(4000)

        listings: list[ProcurementListing] = []

        metadata = await _extract_search_metadata(page)
        if metadata is not None:
            home_path, node_id, token = metadata
            rows = await _fetch_open_tenders(
                context=context,
                listing_url=listing_url,
                base_url=base_url,
                home_path=home_path,
                node_id=node_id,
                token=token,
            )

            for row in rows:
                listing = _row_to_listing(row, base_url, home_path)
                if listing is not None:
                    listings.append(listing)

            listings = deduplicate_listings(listings)

        # Safety fallback: extract from loaded listing HTML if endpoint failed.
        if not listings:
            html_content = await page.content()
            listings = extract_listings_from_html(html_content, portal.name)

        listings = _fix_source_urls(listings, page.url, portal.url)
        listings = await _enrich_with_details(listings, page, portal)

        logger.info(
            "BidsAndTenders scrape complete for '%s': %d listings found",
            portal.name,
            len(listings),
        )

        return BidsAndTendersResult(listings=listings, search_used=False)

    except Exception:
        logger.exception(
            "BidsAndTenders scrape failed for portal '%s' (%s)",
            portal.name,
            listing_url,
        )
        return BidsAndTendersResult(listings=[], search_used=False)

    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.warning(
                    "Failed to close browser for portal '%s'",
                    portal.name,
                )
        if p is not None:
            try:
                await p.stop()
            except Exception:
                pass
