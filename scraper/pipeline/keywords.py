"""
Keyword loading, matching, filtering, and deduplication.

Pure-logic module with no database or orchestrator dependencies.
Used by the pipeline orchestrator for scraper-side filtering and
by the purge function for database cleanup.
"""

import csv
import logging
import random
import re
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


def load_keywords_by_category(
    csv_path: Path = KEYWORDS_CSV_PATH,
) -> dict[str, dict[str, list[str]]]:
    """
    Load keywords from CSV grouped by Category then Language.

    Returns structure like:
        {"Core Language and Translation": {"EN": ["translation", ...], "FR": [...]}, ...}

    Validates file exists, required columns present, and at least one keyword.
    Raises SystemExit if CSV is missing, malformed, or empty.
    """
    if not csv_path.exists():
        logger.error("Keywords CSV not found: %s", csv_path)
        raise SystemExit(f"Keywords CSV not found: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(
            set(reader.fieldnames)
        ):
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            logger.error("Keywords CSV missing columns: %s", missing)
            raise SystemExit(f"Keywords CSV missing required columns: {missing}")

        result: dict[str, dict[str, list[str]]] = {}
        total = 0
        for row in reader:
            keyword = row.get("Keyword", "").strip()
            if not keyword:
                continue
            category = row.get("Category", "").strip()
            language = row.get("Language", "").strip()
            if not category or not language:
                continue
            result.setdefault(category, {}).setdefault(language, []).append(
                keyword.lower()
            )
            total += 1

    if total == 0:
        logger.error("Keywords CSV loaded but contains no keywords")
        raise SystemExit("Keywords CSV contains no keywords")

    logger.info(
        "Loaded %d keywords across %d categories", total, len(result)
    )
    return result


def select_keyword_batch(
    category_keywords: dict[str, list[str]], per_language: int = 5
) -> list[str]:
    """
    Select a random batch of keywords from one category's language dict.

    For each language key ("EN", "FR"), selects min(per_language, available)
    random keywords. Returns a flat combined list.
    """
    batch: list[str] = []
    for lang_keywords in category_keywords.values():
        count = min(per_language, len(lang_keywords))
        batch.extend(random.sample(lang_keywords, count))
    return batch


def matches_keywords(title: Optional[str], description: Optional[str], keywords: list) -> bool:
    """
    Check if a listing matches any keyword via proximity-based word matching.

    For multi-word keywords, all keyword words must appear within a sliding
    window of (keyword_word_count + 3) consecutive text words. This prevents
    false positives where keyword words appear far apart in the text (e.g.
    "language" in boilerplate + "services" in title matching "language services").

    Single-word keywords match if the word appears anywhere in the text.

    Returns True if any keyword matches.
    """
    text = ""
    if title:
        text += title.lower()
    if description:
        text += " " + description.lower()

    if not text.strip():
        return False

    text_word_list = re.findall(r"\w+", text)
    text_word_set = set(text_word_list)

    for kw in keywords:
        kw_words = re.findall(r"\w+", kw)
        if not kw_words:
            continue

        # Quick check: all keyword words must exist somewhere in text
        if not all(word in text_word_set for word in kw_words):
            continue

        # Single-word keyword: presence is sufficient
        if len(kw_words) == 1:
            return True

        # Multi-word keyword: check proximity via sliding window
        window_size = len(kw_words) + 3
        # If text fits in one window, the quick check above is sufficient
        if len(text_word_list) <= window_size:
            return True
        kw_word_set = set(kw_words)
        for i in range(len(text_word_list) - window_size + 1):
            window = set(text_word_list[i:i + window_size])
            if kw_word_set.issubset(window):
                return True

    return False


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
