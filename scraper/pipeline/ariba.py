"""SAP Ariba public listing scrapers for city/province portals."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from scraper import config
from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.keywords import deduplicate_listings

try:
    from playwright.async_api import Page, async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    Page = object  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

EDMONTON_ARIBA_PROFILE_URL = "https://service.ariba.com/Discovery.aw/ad/profile?key=AN01394774623"
TORONTO_CONFIG_URL = "https://www.toronto.ca/app_content/solicitations_public_config/"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _parse_json_from_response_content(content: str) -> dict | list | None:
    """Parse JSON from either raw JSON or JSON wrapped in HTML/pre tags."""
    if not content:
        return None

    stripped = content.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    soup = BeautifulSoup(content, "html.parser")
    text = _normalize_text(soup.get_text(" ")) or ""

    for candidate in (text, stripped):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue

    return None


def _parse_generic_date(value: str | None) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    # Remove trailing timezone abbreviations.
    text = re.sub(r"\s+[A-Z]{2,4}$", "", text)

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if date_match:
        return date_match.group(1)

    for fmt in (
        "%d %b %Y %I:%M %p",
        "%d %b %Y",
        "%b %d, %Y %I:%M %p",
        "%b %d, %Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _split_reference_and_title(title: str) -> tuple[str | None, str]:
    text = _normalize_text(title) or ""
    match = re.match(r"^([A-Za-z0-9\-]{4,})\s*[\-–]\s*(.+)$", text)
    if match:
        return match.group(1), match.group(2)

    match = re.match(r"^(\d{5,})\s+(.+)$", text)
    if match:
        return match.group(1), match.group(2)

    return None, text


def _extract_ariba_profile_listings(
    html_content: str,
    profile_url: str,
    organization_hint: str | None = None,
) -> list[ProcurementListing]:
    """Parse Ariba Discovery profile page listings."""
    soup = BeautifulSoup(html_content, "html.parser")

    listings: list[ProcurementListing] = []

    for title_anchor in soup.select("a.QuoteSearchResultTitle"):
        raw_title = _normalize_text(title_anchor.get_text(" "))
        if not raw_title:
            continue

        reference_number, title = _split_reference_and_title(raw_title)

        title_row = title_anchor.find_parent("tr")
        detail_row = title_row.find_next_sibling("tr") if title_row else None
        category_row = detail_row.find_next_sibling("tr") if detail_row else None

        detail_text = _normalize_text(detail_row.get_text(" ")) if detail_row else None
        category_text = _normalize_text(category_row.get_text(" ")) if category_row else None

        organization = organization_hint
        closing_date = None
        posting_date = None
        category = None

        if detail_text:
            org_match = re.search(r"^(.*?)\s+Posted:\s*", detail_text)
            if org_match:
                organization = _normalize_text(org_match.group(1)) or organization

            posted_match = re.search(r"Posted:\s*([A-Za-z0-9, :\-]+)", detail_text)
            if posted_match:
                posting_date = _parse_generic_date(posted_match.group(1))

            closes_match = re.search(r"Closes:\s*([A-Za-z0-9, :\-]+)", detail_text)
            if closes_match:
                closing_date = _parse_generic_date(closes_match.group(1))

        if category_text:
            match = re.search(r"Product and Service Categories:\s*(.+)$", category_text)
            category = _normalize_text(match.group(1) if match else category_text)

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
                posting_date=posting_date,
                closing_date=closing_date,
                source_url=profile_url,
                source_listing_id=reference_number or f"{profile_url}#{title}",
                status="Open",
                raw_location=organization,
            )
        )

    return listings


async def _load_page_content(page: Page, url: str) -> str:
    await page.goto(url, wait_until="networkidle", timeout=90000)
    await page.wait_for_timeout(1500)
    return await page.content()


async def _scrape_edmonton(page: Page, portal: PortalRecord) -> list[ProcurementListing]:
    content = await _load_page_content(page, portal.url)
    soup = BeautifulSoup(content, "html.parser")

    profile_link = soup.select_one("a[href*='Discovery.aw/ad/profile']")
    profile_url = urljoin(portal.url, profile_link["href"]) if profile_link and profile_link.get("href") else EDMONTON_ARIBA_PROFILE_URL

    profile_content = await _load_page_content(page, profile_url)
    listings = _extract_ariba_profile_listings(profile_content, profile_url, organization_hint="The City of Edmonton")

    logger.info("Portal '%s': Edmonton Ariba scraped %d listings", portal.name, len(listings))
    return listings


def _build_toronto_api_url(config_data: dict) -> str:
    host = (
        config_data.get("httpHost", {})
        .get("app_public", {})
        .get("prod")
        or "https://secure.toronto.ca"
    )

    api_public = (
        config_data.get("api", {}).get("api_public", {}).get("post")
        or config_data.get("api_public", {}).get("post")
        or "/c3api_data/v2/DataAccess.svc/"
    )

    repo = config_data.get("default_repo") or "pmmd_solicitations"

    today = datetime.utcnow().date().isoformat()
    filter_value = (
        "Ready_For_Posting eq 'Yes' and Status eq 'Open' and Closing_Date ge "
        f"{today}"
    )

    query = (
        "$format=application/json;odata.metadata=none"
        "&$count=true"
        "&$skip=0"
        "&$top=200"
        f"&$filter={quote(filter_value, safe="' =")}"  # preserve OData operators and quoted literals
    )

    return f"{host}{api_public}{repo}/feis_solicitation_published?{query}"


def _extract_toronto_records(records: list[dict], api_url: str) -> list[ProcurementListing]:
    listings: list[ProcurementListing] = []

    for record in records:
        title = _normalize_text(record.get("Posting_Title"))
        if not title:
            continue

        reference_number = _normalize_text(record.get("Reference_Number"))
        category = _normalize_text(record.get("High_Level_Category") or record.get("Posting_Type"))
        closing_date = _parse_generic_date(record.get("Closing_Date"))
        posting_date = _parse_generic_date(record.get("Issue_Date"))

        source_url = _normalize_text(record.get("Ariba_Discovery_Posting_Link")) or api_url
        source_listing_id = _normalize_text(record.get("id")) or reference_number or source_url

        description_parts = []
        if category:
            description_parts.append(f"Category: {category}")
        buyer = _normalize_text(record.get("Buyer_Name"))
        if buyer:
            description_parts.append(f"Buyer: {buyer}")

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=reference_number,
                description=" | ".join(description_parts) if description_parts else None,
                posting_date=posting_date,
                closing_date=closing_date,
                source_url=source_url,
                source_listing_id=source_listing_id,
                status="Open",
                raw_location="Toronto, Ontario",
            )
        )

    return listings


async def _scrape_toronto(page: Page, portal: PortalRecord) -> list[ProcurementListing]:
    config_content = await _load_page_content(page, TORONTO_CONFIG_URL)
    parsed = _parse_json_from_response_content(config_content)
    if not isinstance(parsed, dict):
        logger.warning("Portal '%s': unable to parse Toronto portal config", portal.name)
        return []

    api_url = _build_toronto_api_url(parsed)
    api_content = await _load_page_content(page, api_url)
    api_payload = _parse_json_from_response_content(api_content)

    if not isinstance(api_payload, dict):
        logger.warning("Portal '%s': Toronto API payload was not JSON", portal.name)
        return []

    records = api_payload.get("value")
    if not isinstance(records, list):
        return []

    listings = _extract_toronto_records(records, api_url)
    logger.info("Portal '%s': Toronto Ariba scraped %d listings", portal.name, len(listings))
    return listings


def _listing_from_nova_scotia_record(record: dict, portal_url: str) -> ProcurementListing | None:
    title = _normalize_text(record.get("title"))
    if not title:
        return None

    reference_number = _normalize_text(record.get("tenderId"))
    closing_date = _parse_generic_date(record.get("closingDate"))
    posting_date = _parse_generic_date(record.get("issuedDate"))

    category = _normalize_text(record.get("solicitationType"))
    if not category:
        unspsc = record.get("unspscLevelData")
        if isinstance(unspsc, list) and unspsc:
            first = unspsc[0]
            if isinstance(first, dict):
                category = _normalize_text(
                    first.get("unspscLevel4")
                    or first.get("unspscLevel3")
                    or first.get("unspscLevel2")
                    or first.get("unspscLevel1")
                )

    source_url = _normalize_text(record.get("tenderUrl"))
    if not source_url and reference_number:
        source_url = f"{portal_url.rstrip('/')}/tenders/{reference_number}"
    if not source_url:
        source_url = portal_url

    organization = _normalize_text(record.get("procumentEntity") or record.get("procurementEntity"))

    description_parts = []
    if category:
        description_parts.append(f"Category: {category}")
    if organization:
        description_parts.append(f"Organization: {organization}")

    return ProcurementListing(
        title=title,
        reference_number=reference_number,
        description=" | ".join(description_parts) if description_parts else None,
        posting_date=posting_date,
        closing_date=closing_date,
        source_url=source_url,
        source_listing_id=reference_number or source_url,
        status="Open",
        raw_location=organization,
    )


async def _scrape_nova_scotia(page: Page, portal: PortalRecord) -> list[ProcurementListing]:
    await page.goto(portal.url, wait_until="networkidle", timeout=90000)
    await page.wait_for_timeout(4000)

    # First pass: extract any rendered table/card rows directly from DOM.
    dom_rows = await page.evaluate(
        r"""
        () => {
          const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
          const results = [];

          const tables = Array.from(document.querySelectorAll('table'));
          for (const table of tables) {
            const headers = Array.from(table.querySelectorAll('thead th')).map((th) => clean(th.innerText).toLowerCase());
            const bodyRows = Array.from(table.querySelectorAll('tbody tr'));
            for (const tr of bodyRows) {
              const cells = Array.from(tr.querySelectorAll('td')).map((td) => clean(td.innerText));
              if (!cells.length || cells.every((v) => !v)) {
                continue;
              }
              const row = {};
              headers.forEach((h, i) => {
                if (h && cells[i]) {
                  row[h] = cells[i];
                }
              });
              const firstLink = tr.querySelector('a[href]');
              if (firstLink) {
                row.href = firstLink.getAttribute('href');
              }
              if (!row.title && cells[0]) {
                row.title = cells[0];
              }
              results.push(row);
            }
          }

          return results;
        }
        """
    )

    listings: list[ProcurementListing] = []
    for row in dom_rows or []:
        title = _normalize_text(row.get("title") or row.get("tender") or row.get("tender id"))
        if not title:
            continue

        reference = _normalize_text(row.get("tender id") or row.get("id") or row.get("reference"))
        category = _normalize_text(row.get("category") or row.get("type"))
        close_date = _parse_generic_date(row.get("closing date") or row.get("close date"))
        source_url = urljoin(page.url, row.get("href") or "") if row.get("href") else page.url

        listings.append(
            ProcurementListing(
                title=title,
                reference_number=reference,
                description=f"Category: {category}" if category else None,
                posting_date=None,
                closing_date=close_date,
                source_url=source_url,
                source_listing_id=reference or source_url,
                status="Open",
                raw_location="Nova Scotia",
            )
        )

    # Fallback: request tenders JSON through browser context.
    if not listings:
        tender_payload = await page.evaluate(
            """
            async () => {
              try {
                const base = window.env && window.env.BASE_API_URL;
                if (!base) {
                  return null;
                }
                const response = await fetch(`${base}/tenders?page=1&numberOfRecords=100`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: '{}',
                  credentials: 'include',
                });
                if (!response.ok) {
                  return null;
                }
                return await response.json();
              } catch (err) {
                return null;
              }
            }
            """
        )

        if isinstance(tender_payload, dict):
            records = tender_payload.get("tenderDataList")
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        listing = _listing_from_nova_scotia_record(record, portal.url)
                        if listing is not None:
                            listings.append(listing)

    logger.info("Portal '%s': Nova Scotia Ariba scraped %d listings", portal.name, len(listings))
    return listings


def _classify_ariba_portal(portal: PortalRecord) -> str | None:
    name = portal.name.lower()
    url = portal.url.lower()

    if "edmonton" in name or "edmonton" in url:
        return "edmonton"
    if "nova scotia" in name or "novascotia" in url:
        return "nova_scotia"
    if "toronto" in name or "toronto" in url:
        return "toronto"

    return None


async def ariba_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Dispatch scraper for Ariba-backed public listing pages."""
    if async_playwright is None:
        logger.warning("Playwright not installed; returning empty Ariba listing set")
        return []

    portal_type = _classify_ariba_portal(portal)
    if portal_type is None:
        logger.warning("Portal '%s': no Ariba scraper matched URL %s", portal.name, portal.url)
        return []

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await playwright.chromium.launch(headless=config.BROWSER_HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        if portal_type == "edmonton":
            listings = await _scrape_edmonton(page, portal)
        elif portal_type == "toronto":
            listings = await _scrape_toronto(page, portal)
        else:
            listings = await _scrape_nova_scotia(page, portal)

        return deduplicate_listings(listings)

    except Exception:
        logger.exception("Portal '%s': Ariba scrape failed", portal.name)
        return []
    finally:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await playwright.stop()
