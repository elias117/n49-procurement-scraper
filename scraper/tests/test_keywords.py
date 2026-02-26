"""
Tests for the keyword loading, matching, filtering, and deduplication module.

Covers: real CSV loading, fail-safe validation, case-insensitive matching,
French accents, None handling, multi-word phrases, partial matches,
deduplication by source_listing_id.
"""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scraper.models import ListingRecord
from scraper.pipeline.keywords import (
    load_keywords,
    load_keywords_by_category,
    select_keyword_batch,
    matches_keywords,
    filter_listings,
    deduplicate_listings,
)
from scraper.db import purge_unmatched_listings


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
        assert len(keywords) >= 50

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

    def test_words_present_but_not_contiguous(self):
        """Keyword 'translation services' matches even when other words intervene."""
        assert matches_keywords(
            "Translation and Editing Services", None, ["translation services"]
        ) is True

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


# ---------------------------------------------------------------------------
# TestPurge
# ---------------------------------------------------------------------------


class TestPurge:
    """Tests for purge_unmatched_listings()."""

    @pytest.fixture
    def mock_conn(self):
        mock = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock.cursor.return_value = mock_cursor
        mock._mock_cursor = mock_cursor
        return mock

    def test_purge_deletes_non_matching(self, mock_conn):
        mock_cursor = mock_conn._mock_cursor
        mock_cursor.fetchall.return_value = [
            ("id-1", "translation services needed", "description"),
            ("id-2", "office furniture supply", "desks and chairs"),
            ("id-3", "bilingual translation project", None),
        ]
        mock_cursor.rowcount = 1

        result = purge_unmatched_listings(mock_conn, ["translation"])
        assert result == 1

        # Verify DELETE was called with the non-matching ID
        delete_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "DELETE" in str(c)
        ]
        assert len(delete_calls) == 1
        assert "id-2" in delete_calls[0][0][1][0]

    def test_purge_nothing_when_all_match(self, mock_conn):
        mock_cursor = mock_conn._mock_cursor
        mock_cursor.fetchall.return_value = [
            ("id-1", "translation services", "desc"),
            ("id-2", "certified translation", "more desc"),
        ]

        result = purge_unmatched_listings(mock_conn, ["translation"])
        assert result == 0

        # Only SELECT should have been executed, no DELETE
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 1  # Just the SELECT
        assert "SELECT" in str(calls[0])

    def test_purge_uses_matches_keywords(self, mock_conn):
        mock_cursor = mock_conn._mock_cursor
        mock_cursor.fetchall.return_value = [
            ("id-1", "test title", "test desc"),
        ]

        with patch("scraper.pipeline.keywords.matches_keywords") as mock_match:
            mock_match.return_value = True
            purge_unmatched_listings(mock_conn, ["test"])
            mock_match.assert_called_once_with("test title", "test desc", ["test"])

    def test_purge_handles_none_description(self, mock_conn):
        mock_cursor = mock_conn._mock_cursor
        mock_cursor.fetchall.return_value = [
            ("id-1", "translation services", None),
        ]

        # Should not crash
        result = purge_unmatched_listings(mock_conn, ["translation"])
        assert result == 0

    def test_purge_batches_deletes(self, mock_conn):
        mock_cursor = mock_conn._mock_cursor
        # 2500 non-matching rows
        mock_cursor.fetchall.return_value = [
            (f"id-{i}", "office furniture", "no match") for i in range(2500)
        ]
        mock_cursor.rowcount = 1000

        result = purge_unmatched_listings(mock_conn, ["translation"])

        # Should batch into 3 DELETE calls (1000 + 1000 + 500)
        delete_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "DELETE" in str(c)
        ]
        assert len(delete_calls) == 3


# ---------------------------------------------------------------------------
# TestLoadKeywordsByCategory
# ---------------------------------------------------------------------------


class TestLoadKeywordsByCategory:
    def test_loads_from_real_csv(self):
        result = load_keywords_by_category(REAL_CSV)
        assert isinstance(result, dict)
        assert len(result) >= 3

    def test_structure_is_category_then_language(self):
        result = load_keywords_by_category(REAL_CSV)
        for category, lang_dict in result.items():
            assert isinstance(lang_dict, dict)
            for lang, keywords in lang_dict.items():
                assert lang in ("EN", "FR")
                assert isinstance(keywords, list)
                assert all(isinstance(k, str) for k in keywords)

    def test_keywords_are_lowercased(self):
        result = load_keywords_by_category(REAL_CSV)
        for lang_dict in result.values():
            for keywords in lang_dict.values():
                for kw in keywords:
                    assert kw == kw.lower(), f"Keyword not lowercased: {kw}"

    def test_category_counts_match(self):
        result = load_keywords_by_category(REAL_CSV)
        core = result["Core Language and Translation"]
        assert len(core["EN"]) >= 15
        assert len(core["FR"]) >= 14

    def test_fails_on_missing_file(self, tmp_path):
        with pytest.raises(SystemExit):
            load_keywords_by_category(tmp_path / "nonexistent.csv")

    def test_fails_on_empty_keywords(self, tmp_path):
        csv_path = _write_csv(tmp_path)
        with pytest.raises(SystemExit):
            load_keywords_by_category(csv_path)


# ---------------------------------------------------------------------------
# TestSelectKeywordBatch
# ---------------------------------------------------------------------------


class TestSelectKeywordBatch:
    def test_selects_up_to_per_language(self):
        category_kw = {
            "EN": [f"en-kw-{i}" for i in range(10)],
            "FR": [f"fr-kw-{i}" for i in range(10)],
        }
        import random as _random
        _random.seed(42)
        result = select_keyword_batch(category_kw, per_language=5)
        assert len(result) == 10  # 5 EN + 5 FR

    def test_fewer_than_limit_uses_all(self):
        category_kw = {
            "EN": [f"en-kw-{i}" for i in range(10)],
            "FR": [f"fr-kw-{i}" for i in range(3)],
        }
        import random as _random
        _random.seed(42)
        result = select_keyword_batch(category_kw, per_language=5)
        assert len(result) == 8  # 5 EN + 3 FR

    def test_empty_language_skipped(self):
        category_kw = {
            "EN": [f"en-kw-{i}" for i in range(10)],
        }
        import random as _random
        _random.seed(42)
        result = select_keyword_batch(category_kw, per_language=5)
        assert len(result) == 5  # Only EN

    def test_randomness(self):
        category_kw = {
            "EN": [f"en-kw-{i}" for i in range(50)],
            "FR": [f"fr-kw-{i}" for i in range(50)],
        }
        import random as _random
        _random.seed(1)
        result1 = select_keyword_batch(category_kw, per_language=5)
        _random.seed(2)
        result2 = select_keyword_batch(category_kw, per_language=5)
        # With different seeds and large pools, results should differ
        assert result1 != result2

    def test_returns_flat_list(self):
        category_kw = {
            "EN": ["translation", "interpretation"],
            "FR": ["traduction", "interpr\u00e9tation"],
        }
        import random as _random
        _random.seed(42)
        result = select_keyword_batch(category_kw, per_language=5)
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
