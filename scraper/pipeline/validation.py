"""
Post-extraction validation and completeness scoring.

Validates ListingRecord fields and nullifies implausible values rather than
rejecting entire listings. Per user decision: "blank is always better than
a wrong guess."

The ONLY rejection case is a missing title -- no title means no listing.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

from scraper.models import ListingRecord

logger = logging.getLogger("scraper.validation")

# Fields counted for completeness scoring (9 total)
_COMPLETENESS_FIELDS = (
    "title",
    "description",
    "posting_date",
    "closing_date",
    "classification_codes",
    "value_min",
    "contact_info",
    "province",
    "source_url",
)

VALID_STATUSES = {"open", "closed", "cancelled", "awarded"}

# Upper bound for contract values (CAD)
VALUE_UPPER_BOUND = 10_000_000_000  # 10 billion

# Canadian provinces/territories (full names + abbreviations), normalized to
# lowercase for case-insensitive validation.
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

HTTP_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def validate_listing(listing: ListingRecord) -> ListingRecord:
    """
    Validate a ListingRecord by nullifying implausible field values.

    Rules applied in order:
    1. Missing title -> raise ValueError (the ONLY rejection case).
    1b. Missing source_listing_id -> generate deterministic fallback hash.
    2. closing_date < posting_date -> null closing_date.
    3. Unparseable dates -> null them.
    4. Values outside 0-10B range -> null them.
    5. value_max < value_min -> null both.
    6. Invalid status -> default to 'open'.
    7. Classification codes missing system/code keys -> remove entries.
    8. Province not in Canadian province/territory set -> null province.
    9. Invalid URL format -> null source_url.

    Args:
        listing: A ListingRecord to validate.

    Returns:
        The validated ListingRecord with bad fields nullified.

    Raises:
        ValueError: If title is missing or empty.
    """
    # Rule 1: Minimum viable check -- title is required
    if not listing.title or not listing.title.strip():
        raise ValueError("Listing title is required; cannot validate without it.")

    # Rule 1b: source_listing_id fallback
    if not listing.source_listing_id:
        fallback_input = (
            f"{listing.source_portal}:{listing.title}:{listing.source_url or ''}"
        )
        fallback_id = hashlib.sha256(fallback_input.encode()).hexdigest()[:64]
        listing.source_listing_id = fallback_id
        logger.warning(
            "Generated fallback source_listing_id for listing: %s", listing.title
        )

    # Rule 3: Date format validation (must apply BEFORE Rule 2 since Rule 2
    # compares parsed dates)
    listing.posting_date = _validate_date(listing.posting_date, "posting_date")
    listing.closing_date = _validate_date(listing.closing_date, "closing_date")

    # Rule 2: Closing date sanity
    if listing.closing_date is not None and listing.posting_date is not None:
        try:
            closing = datetime.fromisoformat(listing.closing_date)
            posting = datetime.fromisoformat(listing.posting_date)
            if closing < posting:
                logger.warning(
                    "Closing date %s is before posting date %s; nullifying closing_date.",
                    listing.closing_date,
                    listing.posting_date,
                )
                listing.closing_date = None
        except (ValueError, TypeError):
            # Dates already validated in Rule 3, but guard defensively
            pass

    # Rule 4: Value range validation
    if listing.value_min is not None:
        if listing.value_min < 0 or listing.value_min > VALUE_UPPER_BOUND:
            logger.warning(
                "value_min %s outside valid range [0, %s]; nullifying.",
                listing.value_min,
                VALUE_UPPER_BOUND,
            )
            listing.value_min = None

    if listing.value_max is not None:
        if listing.value_max < 0 or listing.value_max > VALUE_UPPER_BOUND:
            logger.warning(
                "value_max %s outside valid range [0, %s]; nullifying.",
                listing.value_max,
                VALUE_UPPER_BOUND,
            )
            listing.value_max = None

    # Rule 5: Value ordering (only if both still present after range check)
    if (
        listing.value_max is not None
        and listing.value_min is not None
        and listing.value_max < listing.value_min
    ):
        logger.warning(
            "value_max %s < value_min %s; nullifying both.",
            listing.value_max,
            listing.value_min,
        )
        listing.value_min = None
        listing.value_max = None

    # Rule 6: Status normalization
    if listing.status is None or listing.status not in VALID_STATUSES:
        if listing.status is not None:
            logger.warning(
                "Invalid status '%s'; defaulting to 'open'.", listing.status
            )
        listing.status = "open"

    # Rule 7: Classification code validation
    if listing.classification_codes is not None:
        valid_codes = []
        for code in listing.classification_codes:
            if isinstance(code, dict) and "system" in code and "code" in code:
                valid_codes.append(code)
            else:
                logger.warning(
                    "Removing classification code entry missing 'system' or 'code' keys: %s",
                    code,
                )
        listing.classification_codes = valid_codes if valid_codes else None

    # Rule 8: Province validation
    if listing.province is not None:
        normalized_province = listing.province.strip().lower()
        if not normalized_province or normalized_province not in CANADIAN_PROVINCES:
            logger.warning(
                "Invalid non-Canadian province '%s'; nullifying province.",
                listing.province,
            )
            listing.province = None

    # Rule 9: URL format validation
    if listing.source_url is not None:
        source_url = listing.source_url.strip()
        if not source_url or not HTTP_URL_RE.match(source_url):
            logger.warning(
                "Invalid URL format '%s'; nullifying source_url.", listing.source_url
            )
            listing.source_url = None
        else:
            listing.source_url = source_url

    return listing


def _validate_date(date_str: Optional[str], field_name: str) -> Optional[str]:
    """
    Validate that a date string can be parsed as ISO format.

    Returns the date string if valid, None otherwise.
    """
    if date_str is None:
        return None

    try:
        datetime.fromisoformat(date_str)
        return date_str
    except (ValueError, TypeError):
        logger.warning(
            "Cannot parse %s value '%s' as ISO datetime; nullifying.",
            field_name,
            date_str,
        )
        return None


def compute_completeness_score(listing: ListingRecord) -> float:
    """
    Compute a completeness score (0.0-1.0) based on how many of the 9
    scored fields are populated.

    Scored fields: title, description, posting_date, closing_date,
    classification_codes (non-empty list), value_min, contact_info,
    province, source_url.

    Args:
        listing: A ListingRecord to score.

    Returns:
        Score rounded to 2 decimal places.
    """
    filled = 0
    for field in _COMPLETENESS_FIELDS:
        value = getattr(listing, field, None)
        if value is None:
            continue
        # classification_codes must be a non-empty list to count
        if field == "classification_codes":
            if isinstance(value, list) and len(value) > 0:
                filled += 1
        else:
            filled += 1

    return round(filled / 9, 2)


def validate_and_score(listing: ListingRecord) -> ListingRecord:
    """
    Convenience function: validate a listing and set its completeness score.

    Args:
        listing: A ListingRecord to validate and score.

    Returns:
        The validated ListingRecord with completeness_score set.
    """
    listing = validate_listing(listing)
    listing.completeness_score = compute_completeness_score(listing)
    return listing
