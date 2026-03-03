"""
LLM-powered extraction of procurement listings from HTML content.

Uses instructor (wrapping OpenAI) for structured extraction with Pydantic
validation and automatic retry. HTML is stripped of non-content elements
before being sent to the LLM to reduce token usage by 5-10x.
"""

import logging
import re
from typing import Optional

import instructor
import openai
from bs4 import BeautifulSoup
from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper import config
from scraper.models import ExtractionResult, ProcurementListing

logger = logging.getLogger(__name__)

# Canadian provinces/territories (full names + abbreviations), normalized to
# lowercase for case-insensitive checks.
CANADIAN_PROVINCES = {
    "alberta",
    "ab",
    "british columbia",
    "bc",
    "manitoba",
    "mb",
    "new brunswick",
    "nb",
    "newfoundland and labrador",
    "nl",
    "nova scotia",
    "ns",
    "ontario",
    "on",
    "prince edward island",
    "pe",
    "quebec",
    "qc",
    "saskatchewan",
    "sk",
    "northwest territories",
    "nt",
    "nunavut",
    "nu",
    "yukon",
    "yt",
}

_NO_RESULTS_MARKERS = (
    "did not match any results",
    "no results found",
    "aucun resultat",
    "aucun résultat",
    "no tenders found",
)

# ---------------------------------------------------------------------------
# System prompt for extraction -- controls quality
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """\
You are a procurement data extraction assistant.
Extract all procurement listings visible on this page.

CRITICAL RULES:
- Only extract fields that are EXPLICITLY stated in the text.
- Return null for any field you cannot find verbatim on the page.
- NEVER guess or infer NAICS codes, UNSPSC codes, GSIN codes, dollar values, or dates.
- If a value is ambiguous or unclear, return null.
- Dates must be in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
- If a value range is stated (e.g., "$50,000 - $100,000"), extract both min and max.
- Include the direct URL to each listing if visible as a link.
- For reference/solicitation numbers, extract exactly as shown.
- Classification codes: only extract if explicitly labeled as NAICS, UNSPSC, GSIN, or commodity code.
- Province must be one of the 13 Canadian provinces/territories (full name). If not clearly Canadian, return null."""

# Tags whose entire content should be removed before extraction
_REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside"}


def strip_html(html_content: str) -> str:
    """
    Strip non-content HTML elements and return clean text.

    Removes script, style, nav, footer, header, and aside tags along with
    most HTML attributes. Preserves href on <a> tags so the LLM can
    extract listing URLs. Extracts text content only, collapsing multiple
    blank lines into single newlines.

    Achieves 5-10x token reduction compared to raw HTML.
    """
    original_size = len(html_content)

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-content tags and their contents
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove HTML attributes to reduce noise, but preserve href on <a> tags
    # so the LLM can extract listing detail URLs.
    for tag in soup.find_all(True):
        if tag.name == "a" and tag.get("href"):
            href = tag["href"]
            tag.attrs = {"href": href}
        else:
            tag.attrs = {}

    # Convert <a> tags to inline text format: "link text [url]"
    # This makes URLs visible to get_text() extraction.
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        link_text = a_tag.get_text(strip=True)
        if href and link_text:
            a_tag.replace_with(f"{link_text} [{href}]")
        elif href:
            a_tag.replace_with(f"[{href}]")

    # Extract text with newline separators
    text = soup.get_text(separator="\n", strip=True)

    # Collapse multiple blank lines into single newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    lowered_text = text.lower()
    if any(marker in lowered_text for marker in _NO_RESULTS_MARKERS):
        logger.info(
            "Detected no-results page marker; returning empty stripped text"
        )
        return ""

    stripped_size = len(text)
    ratio = original_size / stripped_size if stripped_size > 0 else 0

    logger.info(
        "HTML stripped: %d -> %d chars (%.1fx reduction)",
        original_size,
        stripped_size,
        ratio,
    )

    return text


def _should_filter_title(title: str) -> bool:
    """Return True if title looks like a search query artifact/noise."""
    normalized = title.strip()
    if not normalized:
        return True
    if " OR " in normalized:
        return True
    if normalized.lower().startswith("search results for"):
        return True
    if len(normalized) > 300:
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type(
        (openai.RateLimitError, openai.APIConnectionError)
    ),
)
def _call_instructor_extract(
    client, stripped_text: str, portal_name: str
) -> ExtractionResult:
    """
    Call instructor for multi-listing extraction with retry on rate limits.
    """
    return client.chat.completions.create(
        model=config.OPENAI_EXTRACTION_MODEL,
        response_model=ExtractionResult,
        max_retries=2,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract all procurement listings from this "
                    f"{portal_name} page:\n\n{stripped_text}"
                ),
            },
        ],
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type(
        (openai.RateLimitError, openai.APIConnectionError)
    ),
)
def _call_instructor_detail(
    client, stripped_text: str, portal_name: str
) -> ProcurementListing:
    """
    Call instructor for single-listing detail extraction with retry on rate limits.
    """
    return client.chat.completions.create(
        model=config.OPENAI_EXTRACTION_MODEL,
        response_model=ProcurementListing,
        max_retries=2,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract the procurement listing details from this "
                    f"{portal_name} page:\n\n{stripped_text}"
                ),
            },
        ],
    )


def extract_listings_from_html(
    html_content: str, portal_name: str
) -> list[ProcurementListing]:
    """
    Extract procurement listings from raw HTML using instructor + OpenAI.

    1. Strips HTML of non-content elements (5-10x token reduction).
    2. Sends stripped text to GPT-4o-mini via instructor for structured extraction.
    3. Returns list of ProcurementListing objects.

    Returns empty list if HTML is empty or too short (<50 chars after stripping).
    """
    stripped_text = strip_html(html_content)

    if not stripped_text or len(stripped_text) < 50:
        logger.warning(
            "Stripped HTML too short (%d chars) for portal '%s', "
            "returning empty list",
            len(stripped_text),
            portal_name,
        )
        return []

    client = instructor.from_openai(OpenAI())

    result = _call_instructor_extract(client, stripped_text, portal_name)

    filtered_listings = []
    for listing in result.listings:
        if _should_filter_title(listing.title):
            logger.info(
                "Dropping likely query/no-results title for '%s': %s",
                portal_name,
                listing.title[:120],
            )
            continue
        filtered_listings.append(listing)

    logger.info(
        "Extracted %d listings from portal '%s' (%d after title filtering)",
        len(result.listings),
        portal_name,
        len(filtered_listings),
    )

    return filtered_listings


def extract_listing_detail(
    html_content: str, portal_name: str
) -> Optional[ProcurementListing]:
    """
    Extract a single procurement listing from a detail page.

    Same approach as extract_listings_from_html but for individual listing
    pages. Uses ProcurementListing directly as the response model.

    Returns None on failure.
    """
    stripped_text = strip_html(html_content)

    if not stripped_text or len(stripped_text) < 50:
        logger.warning(
            "Stripped HTML too short (%d chars) for portal '%s' detail, "
            "returning None",
            len(stripped_text),
            portal_name,
        )
        return None

    client = instructor.from_openai(OpenAI())

    try:
        listing = _call_instructor_detail(client, stripped_text, portal_name)
        logger.info(
            "Extracted listing detail '%s' from portal '%s'",
            listing.title,
            portal_name,
        )
        return listing
    except Exception:
        logger.exception(
            "Failed to extract listing detail from portal '%s'",
            portal_name,
        )
        return None
