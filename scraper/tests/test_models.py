"""
Tests for Pydantic models in scraper/models.py.
"""

import uuid

import pytest
from pydantic import ValidationError

from scraper.models import (
    ExtractionResult,
    ListingRecord,
    PortalRecord,
    ProcurementListing,
    ScrapeRunRecord,
    to_listing_record,
)


class TestProcurementListing:
    """Tests for the ProcurementListing model (LLM extraction target)."""

    def test_procurement_listing_all_fields(self, sample_listing_dict):
        """Construct with all fields, verify serialization."""
        listing = ProcurementListing(**sample_listing_dict)

        assert listing.title == "IT Infrastructure Modernization Services"
        assert listing.description is not None
        assert listing.reference_number == "EN578-200001/A"
        assert listing.posting_date == "2026-02-01"
        assert listing.closing_date == "2026-03-15"
        assert listing.status == "open"
        assert listing.value_min == 500000.00
        assert listing.value_max == 2000000.00
        assert listing.contact_name == "Jane Smith"
        assert listing.contact_email == "jane.smith@tpsgc-pwgsc.gc.ca"
        assert listing.contact_phone == "613-555-0123"
        assert listing.source_url is not None
        assert listing.source_listing_id == "PW-$$WN-001-78945"
        assert len(listing.classification_codes) == 2
        assert listing.province == "Ontario"
        assert listing.raw_location is not None
        assert len(listing.documents) == 2

        # Verify serialization round-trip
        data = listing.model_dump()
        reconstructed = ProcurementListing(**data)
        assert reconstructed.title == listing.title

    def test_procurement_listing_minimal(self):
        """Construct with only title; all Optional fields should be None."""
        listing = ProcurementListing(title="Minimal Listing")

        assert listing.title == "Minimal Listing"
        assert listing.description is None
        assert listing.reference_number is None
        assert listing.posting_date is None
        assert listing.closing_date is None
        assert listing.status is None
        assert listing.value_min is None
        assert listing.value_max is None
        assert listing.contact_name is None
        assert listing.contact_email is None
        assert listing.contact_phone is None
        assert listing.source_url is None
        assert listing.source_listing_id is None
        assert listing.classification_codes is None
        assert listing.province is None
        assert listing.raw_location is None
        assert listing.documents is None

    def test_procurement_listing_rejects_missing_title(self):
        """Verify ValidationError when title is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ProcurementListing()  # title is required

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) for e in errors)

    def test_classification_codes_jsonb_format(self):
        """Verify classification_codes accepts list of {system, code, description} dicts."""
        codes = [
            {"system": "NAICS", "code": "541512", "description": "Computer Systems Design"},
            {"system": "UNSPSC", "code": "43211500", "description": "Computers"},
            {"system": "GSIN", "code": "N7030", "description": "IT Equipment"},
        ]
        listing = ProcurementListing(
            title="Test Listing",
            classification_codes=codes,
        )
        assert listing.classification_codes == codes
        assert len(listing.classification_codes) == 3
        assert listing.classification_codes[0]["system"] == "NAICS"


class TestListingRecord:
    """Tests for the ListingRecord model (DB-ready)."""

    def test_listing_record_includes_portal_and_embedding(self):
        """Verify ListingRecord accepts embedding list and portal ID."""
        portal_id = str(uuid.uuid4())
        embedding = [0.1] * 1536

        record = ListingRecord(
            title="Test Record",
            source_portal=portal_id,
            source_listing_id="TEST-001",
            embedding=embedding,
            embedding_model="text-embedding-3-small",
        )

        assert record.source_portal == portal_id
        assert record.embedding is not None
        assert len(record.embedding) == 1536
        assert record.embedding_model == "text-embedding-3-small"

    def test_listing_record_null_optional_fields(self):
        """All optional fields accept None without error."""
        portal_id = str(uuid.uuid4())
        record = ListingRecord(
            title="Minimal Record",
            source_portal=portal_id,
            source_listing_id="TEST-002",
        )

        assert record.description is None
        assert record.reference_number is None
        assert record.posting_date is None
        assert record.closing_date is None
        assert record.status is None
        assert record.value_min is None
        assert record.value_max is None
        assert record.contact_info is None
        assert record.amended_date is None
        assert record.embedding is None
        assert record.embedding_model is None
        assert record.language is None
        assert record.classification_codes is None
        assert record.province is None
        assert record.raw_location is None
        assert record.documents is None
        assert record.completeness_score == 0.0


class TestExtractionResult:
    """Tests for the ExtractionResult model."""

    def test_extraction_result_contains_listings(self, sample_listing_dict):
        """Verify ExtractionResult wraps list of ProcurementListing."""
        listing1 = ProcurementListing(**sample_listing_dict)
        listing2 = ProcurementListing(title="Second Listing")

        result = ExtractionResult(listings=[listing1, listing2])

        assert len(result.listings) == 2
        assert result.listings[0].title == "IT Infrastructure Modernization Services"
        assert result.listings[1].title == "Second Listing"

    def test_extraction_result_empty(self):
        """ExtractionResult with no listings is valid."""
        result = ExtractionResult(listings=[])
        assert result.listings == []


class TestPortalRecord:
    """Tests for the PortalRecord model."""

    def test_portal_record_from_dict(self, sample_portal_dict):
        """Construct PortalRecord from dict."""
        portal = PortalRecord(**sample_portal_dict)

        assert portal.name == "CanadaBuys"
        assert portal.level == "federal"
        assert portal.province is None
        assert portal.language == "both"
        assert portal.requires_login is False
        assert portal.enabled is True


class TestToListingRecord:
    """Tests for the to_listing_record factory function."""

    def test_to_listing_record_consolidates_contact_info(self, sample_listing_dict):
        """Verify contact fields are consolidated into contact_info JSONB."""
        extraction = ProcurementListing(**sample_listing_dict)
        portal_id = str(uuid.uuid4())

        record = to_listing_record(extraction, portal_id, "en")

        assert record.source_portal == portal_id
        assert record.language == "en"
        assert record.contact_info == {
            "name": "Jane Smith",
            "email": "jane.smith@tpsgc-pwgsc.gc.ca",
            "phone": "613-555-0123",
        }
        # Verify shared fields copied
        assert record.title == extraction.title
        assert record.description == extraction.description
        assert record.classification_codes == extraction.classification_codes

    def test_to_listing_record_omits_none_contact_fields(self):
        """Contact info omits keys with None values."""
        extraction = ProcurementListing(
            title="Test",
            contact_name="Only Name",
        )
        record = to_listing_record(extraction, "portal-123", "fr")
        assert record.contact_info == {"name": "Only Name"}

    def test_to_listing_record_null_contact_when_all_none(self):
        """Contact info is None when all contact fields are None."""
        extraction = ProcurementListing(title="Test")
        record = to_listing_record(extraction, "portal-123", "en")
        assert record.contact_info is None
