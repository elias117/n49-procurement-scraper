"""
CanadaBuys CSV ingestion handler.

Downloads and parses the CanadaBuys open-data CSV file, mapping each row to a
ListingRecord. This is the zero-cost ingestion path -- no browser automation or
LLM calls required.

Per user decision: "CanadaBuys: use API/open data not browser scraping" and
"Pull everything from CanadaBuys (no API-level filtering)."
"""

import csv
import io
import logging
from typing import Optional

import httpx

from scraper.models import ListingRecord, PortalRecord

logger = logging.getLogger("scraper.canadabuys")

CANADABUYS_CSV_URL = (
    "https://canadabuys.canada.ca/opendata/pub/"
    "openTenderNotice-ouvertAvisAppelOffres.csv"
)
CANADABUYS_TENDER_NOTICE_URL_PREFIX = (
    "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/"
)

# Maps our field names to CanadaBuys CSV column names.
# Source: CanadaBuys open data
# (https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2)
CANADABUYS_FIELD_MAP = {
    # Core fields
    "title": "title-titre-eng",
    "title_fr": "title-titre-fra",
    "description": "tenderDescription-descriptionAppelOffres-eng",
    "description_fr": "tenderDescription-descriptionAppelOffres-fra",
    "reference_number": "referenceNumber-numeroReference",
    "solicitation_number": "solicitationNumber-numeroSollicitation",
    "amendment_number": "amendmentNumber-numeroModification",
    # Dates
    "posting_date": "publicationDate-datePublication",
    "closing_date": "tenderClosingDate-appelOffresDateCloture",
    "amendment_date": "amendmentDate-dateModification",
    "contract_start_date": "expectedContractStartDate-dateDebutContratPrevue",
    "contract_end_date": "expectedContractEndDate-dateFinContratPrevue",
    # Status and classification
    "status": "tenderStatus-appelOffresStatut-eng",
    "gsin": "gsin-nibs",
    "gsin_desc": "gsinDescription-nibsDescription-eng",
    "unspsc": "unspsc",
    "unspsc_desc": "unspscDescription-eng",
    "procurement_category": "procurementCategory-categorieApprovisionnement",
    "notice_type": "noticeType-avisType-eng",
    "procurement_method": "procurementMethod-methodeApprovisionnement-eng",
    # Geography
    "regions_of_opportunity": "regionsOfOpportunity-regionAppelOffres-eng",
    "regions_of_delivery": "regionsOfDelivery-regionsLivraison-eng",
    # Contact
    "contact_name": "contactInfoName-informationsContactNom",
    "contact_email": "contactInfoEmail-informationsContactCourriel",
    "contact_phone": "contactInfoPhone-contactInfoTelephone",
    # Contracting entity
    "entity_name": "contractingEntityName-nomEntitContractante-eng",
    "entity_city": "contractingEntityAddressCity-entiteContractanteAdresseVille-eng",
    "entity_province": (
        "contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng"
    ),
    # URLs
    "notice_url": "noticeURL-URLavis-eng",
    "notice_url_fr": "noticeURL-URLavis-fra",
}

# Procurement category codes
PROCUREMENT_CATEGORIES = {
    "CNST": "Construction",
    "GD": "Goods",
    "SRV": "Services",
    "SRVTGD": "Services related to goods",
}

# CanadaBuys status string -> our status enum
_STATUS_MAP = {
    "open": "open",
    "closed": "closed",
    "cancelled": "cancelled",
    "awarded": "awarded",
    # Common CanadaBuys variations
    "active": "open",
    "expired": "closed",
}


async def canadabuys_ingest(portal: PortalRecord) -> list[ListingRecord]:
    """
    Download the CanadaBuys CSV and parse all rows into ListingRecord objects.

    Args:
        portal: The PortalRecord for CanadaBuys (provides portal.id).

    Returns:
        List of ListingRecord objects, one per valid CSV row.

    Raises:
        httpx.HTTPError: If the CSV download fails.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(CANADABUYS_CSV_URL, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise httpx.HTTPError(
            f"Failed to download CanadaBuys CSV from {CANADABUYS_CSV_URL}: {exc}"
        ) from exc

    # Decode with utf-8-sig to handle BOM (pitfall #5 from research)
    csv_text = response.content.decode("utf-8-sig")

    listings = _parse_csv(csv_text, portal)
    logger.info(
        "CanadaBuys ingest complete: %d listings parsed from CSV.", len(listings)
    )
    return listings


def _parse_csv(csv_text: str, portal: PortalRecord) -> list[ListingRecord]:
    """
    Parse CanadaBuys CSV text into ListingRecord objects.

    Extracted as a separate function for testability (no HTTP calls needed).

    Args:
        csv_text: The raw CSV text content.
        portal: The PortalRecord for CanadaBuys.

    Returns:
        List of ListingRecord objects.
    """
    # Strip BOM if present (handles case where text wasn't decoded with utf-8-sig)
    if csv_text.startswith("\ufeff"):
        csv_text = csv_text[1:]

    reader = csv.DictReader(io.StringIO(csv_text))
    listings = []

    for row in reader:
        # reference_number is REQUIRED -- skip row if missing
        ref_number = _get_field(row, "reference_number")
        if not ref_number:
            logger.warning("Skipping row with missing referenceNumber.")
            continue

        # Title: English preferred, French fallback
        title = _get_field(row, "title") or _get_field(row, "title_fr")
        if not title:
            logger.warning(
                "Skipping row %s: no title in English or French.", ref_number
            )
            continue

        # Detect language from which title was used
        en_title = _get_field(row, "title")
        fr_title = _get_field(row, "title_fr")
        if en_title and fr_title:
            language = "both"
        elif en_title:
            language = "en"
        else:
            language = "fr"

        # Description: English preferred, French fallback
        description = _get_field(row, "description") or _get_field(
            row, "description_fr"
        )

        # Build classification codes
        classification_codes = _build_classification_codes(row)

        # Build contact info
        contact_info = _build_contact_info(row)

        # Source URL: English preferred, French fallback
        source_url = _get_field(row, "notice_url") or _get_field(
            row, "notice_url_fr"
        )
        if source_url is None:
            source_url = (
                f"{CANADABUYS_TENDER_NOTICE_URL_PREFIX}{ref_number}"
            )

        listing = ListingRecord(
            title=title,
            description=description or None,
            reference_number=ref_number,
            source_listing_id=ref_number,
            posting_date=_parse_date(_get_field(row, "posting_date")),
            closing_date=_parse_date(_get_field(row, "closing_date")),
            status=_map_status(_get_field(row, "status")),
            classification_codes=classification_codes or None,
            contact_info=contact_info,
            source_url=source_url,
            province=_get_field(row, "regions_of_opportunity") or None,
            raw_location=_get_field(row, "regions_of_delivery") or None,
            language=language,
            amended_date=_parse_date(_get_field(row, "amendment_date")),
            documents=[],
            source_portal=portal.id,
        )
        listings.append(listing)

    return listings


def _get_field(row: dict, field_name: str) -> Optional[str]:
    """
    Get a field value from a CSV row using the field map.

    Returns None if the field is missing or empty (after stripping).
    """
    column_name = CANADABUYS_FIELD_MAP.get(field_name)
    if column_name is None:
        return None
    value = row.get(column_name, "")
    if isinstance(value, str):
        value = value.strip()
    return value if value else None


def _parse_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parse a date string into ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).

    Handles common formats:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SS
    - YYYY/MM/DD
    - DD/MM/YYYY

    Returns None if the date cannot be parsed.
    """
    if not date_str:
        return None

    from datetime import datetime

    # Try ISO format first (most common for CanadaBuys)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            parsed = datetime.strptime(date_str.strip(), fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning("Cannot parse date: '%s'; returning None.", date_str)
    return None


def _map_status(status_str: Optional[str]) -> str:
    """
    Map a CanadaBuys status string to our enum value.

    Returns 'open' for unrecognized or empty statuses.
    """
    if not status_str:
        return "open"
    return _STATUS_MAP.get(status_str.strip().lower(), "open")


def _build_classification_codes(row: dict) -> list[dict]:
    """
    Extract GSIN and UNSPSC classification codes from a CSV row.

    Returns a list of dicts with keys: system, code, description.
    Only includes entries where the code field is non-empty.
    """
    codes = []

    gsin = _get_field(row, "gsin")
    if gsin:
        codes.append(
            {
                "system": "GSIN",
                "code": gsin,
                "description": _get_field(row, "gsin_desc") or "",
            }
        )

    unspsc = _get_field(row, "unspsc")
    if unspsc:
        codes.append(
            {
                "system": "UNSPSC",
                "code": unspsc,
                "description": _get_field(row, "unspsc_desc") or "",
            }
        )

    return codes


def _build_contact_info(row: dict) -> Optional[dict]:
    """
    Build a contact_info JSONB dict from CSV contact fields.

    Only includes keys with non-empty values.
    Returns None if all contact fields are empty.
    """
    info = {}
    name = _get_field(row, "contact_name")
    email = _get_field(row, "contact_email")
    phone = _get_field(row, "contact_phone")

    if name:
        info["name"] = name
    if email:
        info["email"] = email
    if phone:
        info["phone"] = phone

    return info if info else None
