"""
Tests for the keyword loading, matching, filtering, and deduplication module.

Covers: real CSV loading, fail-safe validation, case-insensitive matching,
French accents, None handling, multi-word phrases, partial matches,
deduplication by source_listing_id.
"""

import uuid
from pathlib import Path

import pytest

from scraper.models import ListingRecord
from scraper.pipeline.keywords import (
    load_keywords,
    matches_keywords,
    filter_listings,
    deduplicate_listings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REAL_CSV = Path(__file__).resolve().parent.parent.parent / "keywords_library.csv"


def _make_listing(title="Test", description=None, source_listing_id=None):
    """Create a minimal ListingRecord for testing."""
    return ListingRecord(
        title=title,
        description=description,
        source_portal=str(uuid.uuid4()),
        source_listing_id=source_listing_id,
    )


def _write_csv(tmp_path, header="Category,Language,Keyword", rows=None):
    """Write a test CSV and return its path."""
    csv_path = tmp_path / "test_keywords.csv"
    lines = [header]
    if rows:
        lines.extend(rows)
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path


# ---------------------------------------------------------------------------
# TestLoadKeywords
# ---------------------------------------------------------------------------


class TestLoadKeywords:
    def test_loads_from_real_csv(self):
        keywords = load_keywords(REAL_CSV)
        assert len(keywords) >= 100

    def test_keywords_are_lowercased(self):
        keywords = load_keywords(REAL_CSV)
        assert all(k == k.lower() for k in keywords)

    def test_contains_english_and_french(self):
        keywords = load_keywords(REAL_CSV)
        assert "translation services" in keywords
        assert "services de traduction" in keywords

    def test_fails_on_missing_file(self, tmp_path):
        with pytest.raises(SystemExit):
            load_keywords(tmp_path / "nonexistent.csv")

    def test_fails_on_missing_columns(self, tmp_path):
        csv_path = _write_csv(tmp_path, header="Name,Value", rows=["foo,bar"])
        with pytest.raises(SystemExit):
            load_keywords(csv_path)

    def test_fails_on_empty_keywords(self, tmp_path):
        csv_path = _write_csv(tmp_path)
        with pytest.raises(SystemExit):
            load_keywords(csv_path)

    def test_strips_whitespace(self, tmp_path):
        csv_path = _write_csv(
            tmp_path,
            rows=["Core,EN,  Translation Services  "],
        )
        keywords = load_keywords(csv_path)
        assert "translation services" in keywords

    def test_skips_empty_keyword_rows(self, tmp_path):
        csv_path = _write_csv(
            tmp_path,
            rows=["Core,EN,translation services", "Core,EN,", "Core,EN,bilingual"],
        )
        keywords = load_keywords(csv_path)
        assert len(keywords) == 2


# ---------------------------------------------------------------------------
# TestMatchesKeywords
# ---------------------------------------------------------------------------


class TestMatchesKeywords:
    def test_matches_in_title(self):
        assert matches_keywords("Translation Services Needed", None, ["translation services"]) is True

    def test_matches_in_description(self):
        assert matches_keywords("RFP", "We need translation services", ["translation services"]) is True

    def test_case_insensitive(self):
        assert matches_keywords("TRANSLATION SERVICES", None, ["translation services"]) is True

    def test_partial_match(self):
        # "translation" is a substring of "mistranslation"
        assert matches_keywords("Fixing a mistranslation issue", None, ["translation"]) is True

    def test_french_accents_exact(self):
        assert matches_keywords("interprétation simultanée requise", None, ["interprétation simultanée"]) is True

    def test_french_accents_mismatch(self):
        # Accented keyword does NOT match non-accented text (substring mismatch)
        assert matches_keywords("Interpretation simultanee", None, ["interprétation simultanée"]) is False

    def test_multi_word_phrase(self):
        assert matches_keywords("We offer bilingual services for government", None, ["bilingual services"]) is True

    def test_no_match(self):
        assert matches_keywords("Office furniture procurement", "Desks and chairs", ["translation services"]) is False

    def test_none_title(self):
        assert matches_keywords(None, "translation services available", ["translation services"]) is True

    def test_none_description(self):
        assert matches_keywords("Translation needed", None, ["translation"]) is True

    def test_both_none(self):
        assert matches_keywords(None, None, ["translation"]) is False

    def test_empty_strings(self):
        assert matches_keywords("", "", ["translation"]) is False


# ---------------------------------------------------------------------------
# TestFilterListings
# ---------------------------------------------------------------------------


class TestFilterListings:
    @pytest.fixture
    def sample_listings(self):
        return [
            _make_listing(title="Translation Services RFP", source_listing_id="L1"),
            _make_listing(title="Office Furniture", source_listing_id="L2"),
            _make_listing(title="Bilingual Support Needed", source_listing_id="L3"),
            _make_listing(title="Parking Lot Maintenance", description="We need translation help", source_listing_id="L4"),
        ]

    def test_filters_to_matching_only(self, sample_listings):
        result = filter_listings(sample_listings, ["translation", "bilingual"])
        assert len(result) == 3

    def test_preserves_order(self, sample_listings):
        result = filter_listings(sample_listings, ["translation", "bilingual"])
        assert result[0].source_listing_id == "L1"
        assert result[1].source_listing_id == "L3"
        assert result[2].source_listing_id == "L4"


# ---------------------------------------------------------------------------
# TestDeduplicateListings
# ---------------------------------------------------------------------------


class TestDeduplicateListings:
    @pytest.fixture
    def dup_listings(self):
        return [
            _make_listing(title="First DUP", source_listing_id="DUP-001"),
            _make_listing(title="Second DUP", source_listing_id="DUP-001"),
            _make_listing(title="Unique", source_listing_id="UNIQUE-001"),
        ]

    def test_removes_duplicates(self, dup_listings):
        result = deduplicate_listings(dup_listings)
        assert len(result) == 2

    def test_keeps_first_occurrence(self, dup_listings):
        result = deduplicate_listings(dup_listings)
        assert result[0].title == "First DUP"

    def test_none_source_listing_id_kept(self):
        listings = [
            _make_listing(title="No ID 1", source_listing_id=None),
            _make_listing(title="No ID 2", source_listing_id=None),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 2

    def test_no_duplicates_returns_all(self):
        listings = [
            _make_listing(title="A", source_listing_id="A1"),
            _make_listing(title="B", source_listing_id="B1"),
            _make_listing(title="C", source_listing_id="C1"),
        ]
        result = deduplicate_listings(listings)
        assert len(result) == 3
