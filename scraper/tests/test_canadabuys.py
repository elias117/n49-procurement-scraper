"""
Tests for CanadaBuys CSV ingestion handler.

Tests the _parse_csv function directly with fixture data to avoid HTTP calls.
Covers field mapping, language fallback, date parsing, status mapping,
classification codes, contact info, and BOM handling.
"""

import uuid

import pytest

from scraper.models import ListingRecord, PortalRecord
from scraper.pipeline.canadabuys import (
    CANADABUYS_FIELD_MAP,
    _build_classification_codes,
    _build_contact_info,
    _map_status,
    _parse_csv,
    _parse_date,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def portal():
    """A CanadaBuys PortalRecord for testing."""
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="CanadaBuys",
        url="https://canadabuys.canada.ca/en/tender-opportunities",
        level="federal",
        province=None,
        language="both",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def sample_csv_content():
    """
    A valid CanadaBuys CSV string with header + 3 rows of realistic data.
    Uses the exact column names from CANADABUYS_FIELD_MAP.
    """
    header = ",".join([
        "referenceNumber-numeroReference",
        "title-titre-eng",
        "title-titre-fra",
        "tenderDescription-descriptionAppelOffres-eng",
        "tenderDescription-descriptionAppelOffres-fra",
        "publicationDate-datePublication",
        "tenderClosingDate-appelOffresDateCloture",
        "amendmentDate-dateModification",
        "tenderStatus-appelOffresStatut-eng",
        "gsin-nibs",
        "gsinDescription-nibsDescription-eng",
        "unspsc",
        "unspscDescription-eng",
        "regionsOfOpportunity-regionAppelOffres-eng",
        "regionsOfDelivery-regionsLivraison-eng",
        "contactInfoName-informationsContactNom",
        "contactInfoEmail-informationsContactCourriel",
        "contactInfoPhone-contactInfoTelephone",
        "noticeURL-URLavis-eng",
        "noticeURL-URLavis-fra",
        "solicitationNumber-numeroSollicitation",
        "amendmentNumber-numeroModification",
        "procurementCategory-categorieApprovisionnement",
        "noticeType-avisType-eng",
        "procurementMethod-methodeApprovisionnement-eng",
    ])

    row1 = ",".join([
        "EN578-200001/A",
        "IT Infrastructure Modernization",
        "Modernisation de l'infrastructure TI",
        "Cloud migration services for federal departments.",
        "Services de migration vers le nuage.",
        "2026-02-01",
        "2026-03-15",
        "",
        "Open",
        "N7030",
        "IT Equipment",
        "43211500",
        "Computers",
        "Ontario",
        "National Capital Region",
        "Jane Smith",
        "jane.smith@gc.ca",
        "613-555-0123",
        "https://canadabuys.canada.ca/en/tender/12345",
        "https://canadabuys.canada.ca/fr/appel-offres/12345",
        "SOL-001",
        "",
        "SRV",
        "RFP",
        "Competitive",
    ])

    row2 = ",".join([
        "PW-22-00987654",
        "Office Furniture Supply",
        "Fourniture de mobilier de bureau",
        "Supply of ergonomic office furniture.",
        "Fourniture de mobilier ergonomique.",
        "2026-01-15",
        "2026-02-28",
        "2026-01-20",
        "Closed",
        "",
        "",
        "56101500",
        "Office Furniture",
        "British Columbia",
        "Vancouver",
        "John Doe",
        "john.doe@gc.ca",
        "",
        "https://canadabuys.canada.ca/en/tender/67890",
        "",
        "SOL-002",
        "001",
        "GD",
        "RFP",
        "Competitive",
    ])

    row3 = ",".join([
        "EP-2026-0042",
        "Environmental Assessment Services",
        "Services d'evaluation environnementale",
        "",
        "Services professionnels d'evaluation.",
        "2026-02-10",
        "",
        "",
        "Active",
        "R099",
        "Professional Services",
        "",
        "",
        "Quebec",
        "Montreal",
        "",
        "",
        "",
        "",
        "https://canadabuys.canada.ca/fr/appel-offres/42",
        "SOL-003",
        "",
        "SRV",
        "ACAN",
        "Non-Competitive",
    ])

    return f"{header}\n{row1}\n{row2}\n{row3}\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseCSV:
    """Tests for _parse_csv()."""

    def test_parse_csv_returns_listings(self, sample_csv_content, portal):
        """Parse sample CSV and verify 3 ListingRecord objects returned."""
        listings = _parse_csv(sample_csv_content, portal)
        assert len(listings) == 3
        assert all(isinstance(l, ListingRecord) for l in listings)

    def test_title_english_preferred(self, sample_csv_content, portal):
        """Row with both English and French titles should use English."""
        listings = _parse_csv(sample_csv_content, portal)
        assert listings[0].title == "IT Infrastructure Modernization"

    def test_title_falls_back_to_french(self, portal):
        """Row with empty English title should use French."""
        header = ",".join([
            "referenceNumber-numeroReference",
            "title-titre-eng",
            "title-titre-fra",
            "tenderDescription-descriptionAppelOffres-eng",
            "tenderDescription-descriptionAppelOffres-fra",
            "publicationDate-datePublication",
            "tenderClosingDate-appelOffresDateCloture",
            "amendmentDate-dateModification",
            "tenderStatus-appelOffresStatut-eng",
            "gsin-nibs",
            "gsinDescription-nibsDescription-eng",
            "unspsc",
            "unspscDescription-eng",
            "regionsOfOpportunity-regionAppelOffres-eng",
            "regionsOfDelivery-regionsLivraison-eng",
            "contactInfoName-informationsContactNom",
            "contactInfoEmail-informationsContactCourriel",
            "contactInfoPhone-contactInfoTelephone",
            "noticeURL-URLavis-eng",
            "noticeURL-URLavis-fra",
            "solicitationNumber-numeroSollicitation",
            "amendmentNumber-numeroModification",
            "procurementCategory-categorieApprovisionnement",
            "noticeType-avisType-eng",
            "procurementMethod-methodeApprovisionnement-eng",
        ])
        row = ",".join([
            "FR-ONLY-001",
            "",  # empty English title
            "Titre en francais seulement",
            "",
            "Description en francais.",
            "2026-02-01",
            "",
            "",
            "Open",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])
        csv_text = f"{header}\n{row}\n"
        listings = _parse_csv(csv_text, portal)

        assert len(listings) == 1
        assert listings[0].title == "Titre en francais seulement"
        assert listings[0].language == "fr"

    def test_missing_reference_number_skipped(self, portal):
        """Row without referenceNumber should be skipped."""
        header = ",".join([
            "referenceNumber-numeroReference",
            "title-titre-eng",
            "title-titre-fra",
            "tenderDescription-descriptionAppelOffres-eng",
            "tenderDescription-descriptionAppelOffres-fra",
            "publicationDate-datePublication",
            "tenderClosingDate-appelOffresDateCloture",
            "amendmentDate-dateModification",
            "tenderStatus-appelOffresStatut-eng",
            "gsin-nibs",
            "gsinDescription-nibsDescription-eng",
            "unspsc",
            "unspscDescription-eng",
            "regionsOfOpportunity-regionAppelOffres-eng",
            "regionsOfDelivery-regionsLivraison-eng",
            "contactInfoName-informationsContactNom",
            "contactInfoEmail-informationsContactCourriel",
            "contactInfoPhone-contactInfoTelephone",
            "noticeURL-URLavis-eng",
            "noticeURL-URLavis-fra",
            "solicitationNumber-numeroSollicitation",
            "amendmentNumber-numeroModification",
            "procurementCategory-categorieApprovisionnement",
            "noticeType-avisType-eng",
            "procurementMethod-methodeApprovisionnement-eng",
        ])
        row = ",".join([
            "",  # empty referenceNumber
            "Some Title",
            "",
            "Some description",
            "",
            "2026-02-01",
            "",
            "",
            "Open",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])
        csv_text = f"{header}\n{row}\n"
        listings = _parse_csv(csv_text, portal)
        assert len(listings) == 0

    def test_classification_codes_built_from_gsin(
        self, sample_csv_content, portal
    ):
        """Row with GSIN code should produce correct classification JSONB."""
        listings = _parse_csv(sample_csv_content, portal)
        # Row 1 has both GSIN and UNSPSC
        codes = listings[0].classification_codes
        assert codes is not None
        assert len(codes) == 2
        assert codes[0]["system"] == "GSIN"
        assert codes[0]["code"] == "N7030"
        assert codes[0]["description"] == "IT Equipment"
        assert codes[1]["system"] == "UNSPSC"
        assert codes[1]["code"] == "43211500"

    def test_contact_info_built(self, sample_csv_content, portal):
        """Row with contact fields should produce correct contact_info JSONB."""
        listings = _parse_csv(sample_csv_content, portal)
        contact = listings[0].contact_info
        assert contact is not None
        assert contact["name"] == "Jane Smith"
        assert contact["email"] == "jane.smith@gc.ca"
        assert contact["phone"] == "613-555-0123"

        # Row 2 has no phone
        contact2 = listings[1].contact_info
        assert contact2 is not None
        assert "phone" not in contact2

    def test_date_parsing(self):
        """Various date formats should be correctly parsed to ISO."""
        assert _parse_date("2026-02-01") == "2026-02-01"
        assert _parse_date("2026-02-01T14:30:00") == "2026-02-01"
        assert _parse_date("2026/02/01") == "2026-02-01"
        assert _parse_date("01/02/2026") == "2026-02-01"
        assert _parse_date("") is None
        assert _parse_date(None) is None
        assert _parse_date("not-a-date") is None

    def test_status_mapping(self):
        """CanadaBuys statuses should map to our enum values."""
        assert _map_status("Open") == "open"
        assert _map_status("Closed") == "closed"
        assert _map_status("Cancelled") == "cancelled"
        assert _map_status("Awarded") == "awarded"
        assert _map_status("Active") == "open"
        assert _map_status("Expired") == "closed"
        assert _map_status("") == "open"
        assert _map_status(None) == "open"
        assert _map_status("UnknownStatus") == "open"

    def test_empty_optional_fields_are_none(self, sample_csv_content, portal):
        """Missing CSV fields should result in None, not empty strings."""
        listings = _parse_csv(sample_csv_content, portal)
        # Row 3 has empty English description and empty closing date
        row3 = listings[2]
        # Description falls back to French
        assert row3.description == "Services professionnels d'evaluation."
        assert row3.closing_date is None
        # Row 3 has no contact info
        assert row3.contact_info is None

    def test_source_url_backfilled_from_source_listing_id_when_missing(self, portal):
        """When notice URL columns are empty, source_url is built from listing id."""
        header = ",".join([
            "referenceNumber-numeroReference",
            "title-titre-eng",
            "title-titre-fra",
            "noticeURL-URLavis-eng",
            "noticeURL-URLavis-fra",
        ])
        row = ",".join([
            "cb-600-32917191",
            "Translation Services for ISCD",
            "",
            "",
            "",
        ])
        csv_text = f"{header}\n{row}\n"

        listings = _parse_csv(csv_text, portal)

        assert len(listings) == 1
        assert listings[0].source_listing_id == "cb-600-32917191"
        assert (
            listings[0].source_url
            == "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-600-32917191"
        )

    def test_utf8_bom_handled(self, portal):
        """CSV with BOM prefix should parse correctly."""
        header = ",".join([
            "referenceNumber-numeroReference",
            "title-titre-eng",
            "title-titre-fra",
            "tenderDescription-descriptionAppelOffres-eng",
            "tenderDescription-descriptionAppelOffres-fra",
            "publicationDate-datePublication",
            "tenderClosingDate-appelOffresDateCloture",
            "amendmentDate-dateModification",
            "tenderStatus-appelOffresStatut-eng",
            "gsin-nibs",
            "gsinDescription-nibsDescription-eng",
            "unspsc",
            "unspscDescription-eng",
            "regionsOfOpportunity-regionAppelOffres-eng",
            "regionsOfDelivery-regionsLivraison-eng",
            "contactInfoName-informationsContactNom",
            "contactInfoEmail-informationsContactCourriel",
            "contactInfoPhone-contactInfoTelephone",
            "noticeURL-URLavis-eng",
            "noticeURL-URLavis-fra",
            "solicitationNumber-numeroSollicitation",
            "amendmentNumber-numeroModification",
            "procurementCategory-categorieApprovisionnement",
            "noticeType-avisType-eng",
            "procurementMethod-methodeApprovisionnement-eng",
        ])
        row = ",".join([
            "BOM-TEST-001",
            "BOM Test Title",
            "",
            "BOM test description",
            "",
            "2026-02-01",
            "",
            "",
            "Open",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "https://example.com/bom",
            "",
            "",
            "",
            "",
            "",
            "",
        ])
        # Prepend BOM character (the utf-8-sig BOM: \xef\xbb\xbf)
        csv_with_bom = "\ufeff" + f"{header}\n{row}\n"

        listings = _parse_csv(csv_with_bom, portal)
        assert len(listings) == 1
        assert listings[0].source_listing_id == "BOM-TEST-001"
        assert listings[0].title == "BOM Test Title"
