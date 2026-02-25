"""
Keyword loading, matching, filtering, and deduplication.

Pure-logic module with no database or orchestrator dependencies.
Used by the pipeline orchestrator for scraper-side filtering and
by the purge function for database cleanup.
"""

import csv
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scraper.keywords")

KEYWORDS_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "keywords_library.csv"

REQUIRED_COLUMNS = {"Category", "Language", "Keyword"}


def load_keywords(csv_path: Path = KEYWORDS_CSV_PATH) -> list[str]:
    """
    Load keywords from CSV and return lowercased keyword strings.

    Validates file exists, required columns present, and at least one keyword.
    Raises SystemExit if CSV is missing, malformed, or empty.
    """
    if not csv_path.exists():
        logger.error("Keywords CSV not found: %s", csv_path)
        raise SystemExit(f"Keywords CSV not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            logger.error("Keywords CSV missing columns: %s", missing)
            raise SystemExit(f"Keywords CSV missing required columns: {missing}")

        keywords = []
        for row in reader:
            keyword = row.get("Keyword", "").strip()
            if keyword:
                keywords.append(keyword.lower())

    if not keywords:
        logger.error("Keywords CSV loaded but contains no keywords")
        raise SystemExit("Keywords CSV contains no keywords")

    logger.info("Loaded %d keywords from %s", len(keywords), csv_path.name)
    return keywords


def matches_keywords(title: Optional[str], description: Optional[str], keywords: list) -> bool:
    """
    Check if a listing matches any keyword via case-insensitive substring.

    Returns True if any keyword is a substring of title or description.
    """
    text = ""
    if title:
        text += title.lower()
    if description:
        text += " " + description.lower()

    if not text.strip():
        return False

    return any(kw in text for kw in keywords)


def filter_listings(listings: list, keywords: list[str]) -> list:
    """
    Filter a list of ListingRecord objects, keeping only keyword matches.

    Logs total vs matched count for observability.
    """
    matched = [
        listing for listing in listings
        if matches_keywords(listing.title, listing.description, keywords)
    ]
    logger.info(
        "Keyword filter: %d listings parsed, %d matched keywords",
        len(listings),
        len(matched),
    )
    return matched


def deduplicate_listings(listings: list) -> list:
    """
    Remove duplicate listings by source_listing_id within a batch.

    Keeps first occurrence, skips subsequent duplicates.
    Listings with None source_listing_id are always kept.
    """
    seen = set()
    unique = []
    for listing in listings:
        lid = listing.source_listing_id
        if lid and lid in seen:
            continue
        if lid:
            seen.add(lid)
        unique.append(listing)

    dupes = len(listings) - len(unique)
    if dupes > 0:
        logger.info("Deduplication: removed %d duplicate listings", dupes)
    return unique
