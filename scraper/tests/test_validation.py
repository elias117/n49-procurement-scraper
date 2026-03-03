"""
Tests for post-extraction validation and completeness scoring.

Covers all validation rules from scraper/pipeline/validation.py:
- Minimum viable check (title required)
- source_listing_id fallback generation
- Date sanity and format validation
- Value range and ordering checks
- Status normalization
- Classification code validation
- URL format validation
- Completeness scoring
"""

import hashlib
import uuid

import pytest

from scraper.models import ListingRecord
from scraper.pipeline.validation import (
    compute_completeness_score,
    validate_and_score,
    validate_listing,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_listing(**overrides) -> ListingRecord:
    """Create a ListingRecord with sensible defaults, overridable by kwargs."""
    defaults = {
        "title": "IT Infrastructure Modernization Services",
        "description": "Cloud migration and server consolidation.",
        "posting_date": "2026-02-01",
        "closing_date": "2026-03-15",
        "status": "open",
        "value_min": 500_000.0,
        "value_max": 2_000_000.0,
        "source_url": "https://canadabuys.canada.ca/en/tender/12345",
        "source_listing_id": "PW-WN-001-78945",
        "source_portal": str(uuid.uuid4()),
        "classification_codes": [
            {"system": "GSIN", "code": "N7030", "description": "IT Equipment"},
        ],
        "province": "Ontario",
        "contact_info": {"name": "Jane Smith", "email": "jane@gc.ca"},
    }
    defaults.update(overrides)
    return ListingRecord(**defaults)


# ---------------------------------------------------------------------------
# Validation rule tests
# ---------------------------------------------------------------------------


class TestValidateListing:
    """Tests for validate_listing()."""

    def test_valid_listing_passes_unchanged(self):
        """A fully valid listing should pass through without modifications."""
        listing = _make_listing()
        original_title = listing.title
        original_posting = listing.posting_date
        original_closing = listing.closing_date
        original_vmin = listing.value_min
        original_vmax = listing.value_max
        original_status = listing.status
        original_url = listing.source_url
        original_codes = listing.classification_codes

        result = validate_listing(listing)

        assert result.title == original_title
        assert result.posting_date == original_posting
        assert result.closing_date == original_closing
        assert result.value_min == original_vmin
        assert result.value_max == original_vmax
        assert result.status == original_status
        assert result.source_url == original_url
        assert result.classification_codes == original_codes

    def test_missing_title_raises(self):
        """ValueError should be raised when title is empty or None."""
        # Empty string title
        listing = _make_listing(title="")
        with pytest.raises(ValueError, match="title is required"):
            validate_listing(listing)

        # Whitespace-only title
        listing2 = _make_listing(title="   ")
        with pytest.raises(ValueError, match="title is required"):
            validate_listing(listing2)

    def test_closing_before_posting_nullified(self):
        """closing_date should be set to None when it is before posting_date."""
        listing = _make_listing(
            posting_date="2026-03-15",
            closing_date="2026-02-01",
        )
        result = validate_listing(listing)

        assert result.closing_date is None
        assert result.posting_date == "2026-03-15"

    def test_negative_value_nullified(self):
        """value_min with a negative value should be set to None."""
        listing = _make_listing(value_min=-100.0)
        result = validate_listing(listing)
        assert result.value_min is None

    def test_huge_value_nullified(self):
        """value_max exceeding 10B should be set to None."""
        listing = _make_listing(value_max=20_000_000_000.0)
        result = validate_listing(listing)
        assert result.value_max is None

    def test_value_max_less_than_min_both_nullified(self):
        """Both value_min and value_max should be None when max < min."""
        listing = _make_listing(value_min=1_000_000.0, value_max=500_000.0)
        result = validate_listing(listing)
        assert result.value_min is None
        assert result.value_max is None

    def test_invalid_status_defaults_to_open(self):
        """An unrecognized status should default to 'open'."""
        listing = _make_listing(status="draft")
        result = validate_listing(listing)
        assert result.status == "open"

    def test_invalid_url_nullified(self):
        """source_url without http(s):// prefix should be set to None."""
        listing = _make_listing(source_url="not-a-url")
        result = validate_listing(listing)
        assert result.source_url is None

    def test_valid_https_url_with_query_params_kept(self):
        """HTTPS URLs with query params should remain valid."""
        listing = _make_listing(
            source_url="https://seao.ca/tenders/detail?id=123&lang=fr"
        )
        result = validate_listing(listing)
        assert result.source_url == "https://seao.ca/tenders/detail?id=123&lang=fr"

    def test_invalid_province_nullified(self):
        """Non-Canadian province values should be nullified."""
        listing = _make_listing(province="Albania")
        result = validate_listing(listing)
        assert result.province is None

    def test_valid_province_abbreviation_preserved(self):
        """Canadian province abbreviations remain valid."""
        listing = _make_listing(province="qc")
        result = validate_listing(listing)
        assert result.province == "qc"

    def test_classification_codes_missing_keys_removed(self):
        """Entries without 'system' or 'code' keys should be removed."""
        listing = _make_listing(
            classification_codes=[
                {"system": "GSIN", "code": "N7030", "description": "IT Equipment"},
                {"description": "Missing system and code"},
                {"system": "NAICS"},  # missing 'code'
            ]
        )
        result = validate_listing(listing)
        assert len(result.classification_codes) == 1
        assert result.classification_codes[0]["system"] == "GSIN"

    def test_missing_source_listing_id_generates_fallback(self):
        """A listing with no source_listing_id gets a deterministic hash fallback."""
        portal_id = str(uuid.uuid4())
        listing = _make_listing(
            source_listing_id=None,
            source_portal=portal_id,
            title="Test Listing",
            source_url="https://example.com/test",
        )
        result = validate_listing(listing)

        assert result.source_listing_id is not None
        assert len(result.source_listing_id) == 64  # SHA-256 hex truncated to 64

    def test_fallback_source_listing_id_is_deterministic(self):
        """Same title+portal+url always produces the same fallback ID."""
        portal_id = str(uuid.uuid4())
        kwargs = {
            "source_listing_id": None,
            "source_portal": portal_id,
            "title": "Deterministic Test",
            "source_url": "https://example.com/det",
        }

        listing1 = _make_listing(**kwargs)
        listing2 = _make_listing(**kwargs)

        result1 = validate_listing(listing1)
        result2 = validate_listing(listing2)

        assert result1.source_listing_id == result2.source_listing_id

        # Verify it matches the expected hash
        expected_input = f"{portal_id}:Deterministic Test:https://example.com/det"
        expected_hash = hashlib.sha256(expected_input.encode()).hexdigest()[:64]
        assert result1.source_listing_id == expected_hash


# ---------------------------------------------------------------------------
# Completeness score tests
# ---------------------------------------------------------------------------


class TestCompletenessScore:
    """Tests for compute_completeness_score()."""

    def test_completeness_score_full(self):
        """All 9 scored fields present should produce 1.0."""
        listing = _make_listing()
        score = compute_completeness_score(listing)
        assert score == 1.0

    def test_completeness_score_minimal(self):
        """Only title + source_url should produce 2/9 = 0.22."""
        listing = _make_listing(
            description=None,
            posting_date=None,
            closing_date=None,
            classification_codes=None,
            value_min=None,
            contact_info=None,
            province=None,
        )
        score = compute_completeness_score(listing)
        assert score == round(2 / 9, 2)

    def test_completeness_score_empty_codes_not_counted(self):
        """An empty classification_codes list should count as missing."""
        listing = _make_listing(classification_codes=[])
        score = compute_completeness_score(listing)
        # 8 of 9 fields present (classification_codes is empty)
        assert score == round(8 / 9, 2)


# ---------------------------------------------------------------------------
# Convenience function test
# ---------------------------------------------------------------------------


class TestValidateAndScore:
    """Tests for validate_and_score()."""

    def test_validate_and_score_sets_score(self):
        """Verify completeness_score is set on the returned listing."""
        listing = _make_listing()
        result = validate_and_score(listing)

        assert result.completeness_score == 1.0
        # Also verify validation ran (status is still valid)
        assert result.status == "open"

    def test_validate_and_score_invalid_date(self):
        """Verify that an invalid date is nullified and score reflects it."""
        listing = _make_listing(posting_date="not-a-date")
        result = validate_and_score(listing)

        assert result.posting_date is None
        # Score: 8 of 9 fields present
        assert result.completeness_score == round(8 / 9, 2)
