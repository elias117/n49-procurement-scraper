"""
Tests for the pipeline orchestrator.

Tests cover: portal classification, dispatch, error isolation, flow order,
and pipeline-level portal filtering. All external dependencies are mocked.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from scraper.models import (
    ListingRecord,
    PortalRecord,
    ProcurementListing,
)
from scraper.pipeline.bidsandtenders import BidsAndTendersResult
from scraper.pipeline.browser_scraper import BrowserScrapeResult
from scraper.pipeline.orchestrator import (
    classify_portal,
    scrape_portal,
    process_portal,
    run_pipeline,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def canadabuys_portal():
    return PortalRecord(
        id="portal-cb-001",
        name="CanadaBuys",
        url="https://canadabuys.canada.ca",
        level="federal",
        province=None,
        language="both",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def bidsandtenders_portal():
    return PortalRecord(
        id="portal-bt-001",
        name="Mississauga Bids",
        url="https://mississauga.bidsandtenders.ca",
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def generic_portal():
    return PortalRecord(
        id="portal-gen-001",
        name="Generic Portal",
        url="https://procurement.example.com/opportunities",
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def seao_portal():
    return PortalRecord(
        id="portal-seao-001",
        name="SEAO Quebec",
        url="https://seao.gouv.qc.ca/avis-resultat-recherche",
        level="provincial",
        province="Quebec",
        language="fr",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def merx_portal():
    return PortalRecord(
        id="portal-merx-001",
        name="Ottawa MERX",
        url="https://www.merx.com/cityofottawa",
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def tier3_portal():
    return PortalRecord(
        id="portal-tier3-001",
        name="Windsor",
        url="https://opendata.citywindsor.ca/Tools/BidsAndTenders",
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def ariba_portal():
    return PortalRecord(
        id="portal-ariba-001",
        name="Toronto Ariba",
        url="https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/",
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def apc_portal():
    return PortalRecord(
        id="portal-apc-001",
        name="APC",
        url="https://vendor.purchasingconnection.ca/",
        level="provincial",
        province="Alberta",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def sasktenders_portal():
    return PortalRecord(
        id="portal-sk-001",
        name="SaskTenders",
        url="https://www.sasktenders.ca/",
        level="provincial",
        province="Saskatchewan",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def bcbid_portal():
    return PortalRecord(
        id="portal-bcbid-001",
        name="BC Bid",
        url="https://www.bcbid.gov.bc.ca/",
        level="provincial",
        province="British Columbia",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def nbon_portal():
    return PortalRecord(
        id="portal-nbon-001",
        name="NBON",
        url="https://nbon-rpanb.gnb.ca/",
        level="provincial",
        province="New Brunswick",
        language="en",
        requires_login=False,
        enabled=True,
    )


@pytest.fixture
def sample_listing_record():
    return ListingRecord(
        title="Test Listing",
        description="A test procurement listing",
        source_portal="portal-cb-001",
        source_listing_id="REF-001",
        language="en",
    )


@pytest.fixture
def sample_procurement_listing():
    return ProcurementListing(
        title="Test Procurement",
        description="A test procurement",
        source_listing_id="REF-002",
    )


@pytest.fixture
def mock_conn():
    return MagicMock()


# ---------------------------------------------------------------------------
# classify_portal tests
# ---------------------------------------------------------------------------


class TestClassifyPortal:
    def test_classify_canadabuys(self, canadabuys_portal):
        """CanadaBuys portal is classified as 'canadabuys'."""
        assert classify_portal(canadabuys_portal) == "canadabuys"

    def test_classify_bidsandtenders(self, bidsandtenders_portal):
        """BidsAndTenders URL returns 'bidsandtenders'."""
        assert classify_portal(bidsandtenders_portal) == "bidsandtenders"

    def test_classify_seao(self, seao_portal):
        """SEAO URL returns 'seao'."""
        assert classify_portal(seao_portal) == "seao"

    def test_classify_merx(self, merx_portal):
        """MERX URL returns 'merx'."""
        assert classify_portal(merx_portal) == "merx"

    def test_classify_tier3(self, tier3_portal):
        """Tier 3 city URL returns 'tier3'."""
        assert classify_portal(tier3_portal) == "tier3"

    def test_classify_ariba(self, ariba_portal):
        """Ariba-backed city page URL returns 'ariba'."""
        assert classify_portal(ariba_portal) == "ariba"

    def test_classify_apc(self, apc_portal):
        """APC URL returns 'apc'."""
        assert classify_portal(apc_portal) == "apc"

    def test_classify_sasktenders(self, sasktenders_portal):
        """SaskTenders URL returns 'sasktenders'."""
        assert classify_portal(sasktenders_portal) == "sasktenders"

    def test_classify_bcbid(self, bcbid_portal):
        """BC Bid URL returns 'bcbid'."""
        assert classify_portal(bcbid_portal) == "bcbid"

    def test_classify_nbon(self, nbon_portal):
        """NBON URL returns 'nbon'."""
        assert classify_portal(nbon_portal) == "nbon"

    def test_classify_other(self, generic_portal):
        """Non-CanadaBuys, non-BidsAndTenders portal returns 'browser'."""
        assert classify_portal(generic_portal) == "browser"

    def test_classify_canadabuys_not_by_url(self):
        """Classification uses name, not URL, for CanadaBuys."""
        portal = PortalRecord(
            id="p1",
            name="SomePortal",
            url="https://canadabuys.example.com",
            level="federal",
            language="en",
            requires_login=False,
            enabled=True,
        )
        # Name is not "CanadaBuys" and URL doesn't contain "bidsandtenders"
        assert classify_portal(portal) == "browser"


# ---------------------------------------------------------------------------
# scrape_portal dispatch tests
# ---------------------------------------------------------------------------


class TestScrapePortal:
    @patch(
        "scraper.pipeline.orchestrator.canadabuys_ingest",
        new_callable=AsyncMock,
    )
    def test_dispatch_canadabuys(self, mock_ingest, canadabuys_portal):
        """CanadaBuys dispatches to canadabuys_ingest and returns (listings, False)."""
        mock_ingest.return_value = []

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(canadabuys_portal)
        )

        mock_ingest.assert_called_once_with(canadabuys_portal)
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.bidsandtenders_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_bidsandtenders(self, mock_scrape, bidsandtenders_portal):
        """BidsAndTenders dispatches to bidsandtenders_scrape with keywords_by_category."""
        mock_scrape.return_value = BidsAndTendersResult(listings=[], search_used=False)

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(bidsandtenders_portal)
        )

        mock_scrape.assert_called_once_with(
            bidsandtenders_portal, keywords_by_category=None
        )
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.bidsandtenders_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_bidsandtenders_with_keywords(self, mock_scrape, bidsandtenders_portal):
        """BidsAndTenders passes keywords_by_category through to scraper."""
        kw_by_cat = {"Cat1": {"EN": ["test"]}}
        mock_scrape.return_value = BidsAndTendersResult(listings=[], search_used=True)

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(bidsandtenders_portal, keywords_by_category=kw_by_cat)
        )

        mock_scrape.assert_called_once_with(
            bidsandtenders_portal, keywords_by_category=kw_by_cat
        )

    @patch(
        "scraper.pipeline.orchestrator.seao_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_seao(self, mock_scrape, seao_portal):
        """SEAO portals dispatch to seao_scrape."""
        mock_listing = ProcurementListing(
            title="SEAO Listing",
            source_listing_id="SEAO-001",
        )
        mock_scrape.return_value = [mock_listing]

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(seao_portal)
        )

        mock_scrape.assert_called_once_with(
            seao_portal, keywords_by_category=None
        )
        assert listings == [mock_listing]
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.merx_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_merx(self, mock_scrape, merx_portal):
        """MERX portals dispatch to merx_scrape."""
        mock_listing = ProcurementListing(
            title="MERX Listing",
            source_listing_id="MERX-001",
        )
        mock_scrape.return_value = [mock_listing]

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(merx_portal)
        )

        mock_scrape.assert_called_once_with(merx_portal)
        assert listings == [mock_listing]
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.tier3_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_tier3(self, mock_scrape, tier3_portal):
        """Tier 3 portals dispatch to tier3_scrape."""
        mock_listing = ProcurementListing(
            title="Windsor Listing",
            source_listing_id="WIN-001",
        )
        mock_scrape.return_value = [mock_listing]

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(tier3_portal)
        )

        mock_scrape.assert_called_once_with(tier3_portal)
        assert listings == [mock_listing]
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.ariba_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_ariba(self, mock_scrape, ariba_portal):
        """Ariba portals dispatch to ariba_scrape."""
        mock_listing = ProcurementListing(
            title="Ariba Listing",
            source_listing_id="ARIBA-001",
        )
        mock_scrape.return_value = [mock_listing]

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(ariba_portal)
        )

        mock_scrape.assert_called_once_with(ariba_portal)
        assert listings == [mock_listing]
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.apc_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_apc(self, mock_scrape, apc_portal):
        """APC portals dispatch to apc_scrape."""
        mock_scrape.return_value = []

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(apc_portal)
        )

        mock_scrape.assert_called_once_with(apc_portal)
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.sasktenders_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_sasktenders(self, mock_scrape, sasktenders_portal):
        """SaskTenders portals dispatch to sasktenders_scrape."""
        mock_scrape.return_value = []

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(sasktenders_portal)
        )

        mock_scrape.assert_called_once_with(sasktenders_portal)
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.bcbid_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_bcbid(self, mock_scrape, bcbid_portal):
        """BC Bid portals dispatch to bcbid_scrape."""
        mock_scrape.return_value = []

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(bcbid_portal)
        )

        mock_scrape.assert_called_once_with(bcbid_portal)
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.nbon_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_nbon(self, mock_scrape, nbon_portal):
        """NBON portals dispatch to nbon_scrape."""
        mock_scrape.return_value = []

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(nbon_portal)
        )

        mock_scrape.assert_called_once_with(nbon_portal)
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.bidsandtenders_scrape",
        new_callable=AsyncMock,
    )
    def test_scrape_portal_returns_search_used_flag(self, mock_scrape, bidsandtenders_portal):
        """scrape_portal returns search_used=True when BidsAndTenders search was used."""
        mock_listing = ProcurementListing(
            title="Test", source_listing_id="BT-001"
        )
        mock_scrape.return_value = BidsAndTendersResult(
            listings=[mock_listing], search_used=True
        )

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(
                bidsandtenders_portal,
                keywords_by_category={"Cat": {"EN": ["test"]}},
            )
        )

        assert listings == [mock_listing]
        assert search_used is True

    @patch(
        "scraper.pipeline.orchestrator.browser_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_browser(self, mock_scrape, generic_portal):
        """Generic portal dispatches to browser_scrape and returns (listings, False)."""
        mock_scrape.return_value = BrowserScrapeResult(listings=[], search_used=False)

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(generic_portal)
        )

        mock_scrape.assert_called_once_with(generic_portal, keywords_by_category=None)
        assert listings == []
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.browser_scrape",
        new_callable=AsyncMock,
    )
    def test_scrape_portal_non_bidsandtenders_returns_search_used_false(
        self, mock_scrape, generic_portal
    ):
        """Non-BidsAndTenders portals return search_used from BrowserScrapeResult."""
        mock_listing = ListingRecord(
            title="Test", source_portal="portal-gen-001",
            source_listing_id="GEN-001", language="en",
        )
        mock_scrape.return_value = BrowserScrapeResult(
            listings=[mock_listing], search_used=False
        )

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(generic_portal)
        )

        assert listings == [mock_listing]
        assert search_used is False

    @patch(
        "scraper.pipeline.orchestrator.browser_scrape",
        new_callable=AsyncMock,
    )
    def test_dispatch_browser_with_keywords(self, mock_scrape, generic_portal):
        """Browser portals pass keywords_by_category through to browser_scrape."""
        kw_by_cat = {"Cat1": {"EN": ["translation"]}}
        mock_scrape.return_value = BrowserScrapeResult(listings=[], search_used=True)

        listings, search_used = asyncio.get_event_loop().run_until_complete(
            scrape_portal(generic_portal, keywords_by_category=kw_by_cat)
        )

        mock_scrape.assert_called_once_with(
            generic_portal, keywords_by_category=kw_by_cat
        )
        assert search_used is True


# ---------------------------------------------------------------------------
# process_portal tests
# ---------------------------------------------------------------------------


class TestProcessPortal:
    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_process_portal_catches_exceptions(
        self,
        mock_scrape,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_complete,
        mock_conn,
        canadabuys_portal,
    ):
        """Failed portal returns error stats instead of raising."""
        mock_start.return_value = "run-id"
        mock_scrape.side_effect = RuntimeError("Network error")

        # Patch fail_run to avoid DB calls
        with patch("scraper.pipeline.orchestrator.fail_run") as mock_fail:
            result = asyncio.get_event_loop().run_until_complete(
                process_portal(mock_conn, canadabuys_portal)
            )

        assert result["error"] == "Network error"
        assert result["found"] == 0
        assert result["new"] == 0
        assert result["updated"] == 0

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_pipeline_flow_order(
        self,
        mock_scrape,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        canadabuys_portal,
    ):
        """Pipeline steps run in order: scrape -> validate -> embed -> upsert."""
        # Set up the call chain
        mock_start.return_value = "run-id"

        test_listing = ListingRecord(
            title="Test",
            source_portal="portal-cb-001",
            source_listing_id="REF-001",
            language="en",
        )
        mock_scrape.return_value = ([test_listing], False)
        mock_validate.return_value = test_listing
        mock_embed.return_value = [test_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        result = asyncio.get_event_loop().run_until_complete(
            process_portal(mock_conn, canadabuys_portal)
        )

        # Verify call order
        mock_scrape.assert_called_once()
        mock_validate.assert_called_once()
        mock_embed.assert_called_once()
        mock_upsert.assert_called_once()
        mock_complete.assert_called_once()
        mock_fail.assert_not_called()

        assert result["found"] == 1
        assert result["new"] == 1

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_process_portal_converts_procurement_listing(
        self,
        mock_scrape,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        generic_portal,
    ):
        """ProcurementListing items are converted to ListingRecord."""
        mock_start.return_value = "run-id"

        # Browser scrapers return ProcurementListing, not ListingRecord
        proc_listing = ProcurementListing(
            title="Browser Listing",
            source_listing_id="BL-001",
            province="Kosovo",
        )
        mock_scrape.return_value = ([proc_listing], False)

        # validate_and_score receives a ListingRecord (converted)
        def validate_side_effect(record):
            assert isinstance(record, ListingRecord)
            assert record.source_portal == "portal-gen-001"
            assert record.province == "British Columbia"
            return record

        mock_validate.side_effect = validate_side_effect
        mock_embed.return_value = []
        mock_upsert.return_value = {"found": 0, "new": 0, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(mock_conn, generic_portal)
        )

        mock_validate.assert_called_once()

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_process_portal_skips_invalid_listings(
        self,
        mock_scrape,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        canadabuys_portal,
    ):
        """Listings that fail validation (ValueError) are skipped."""
        mock_start.return_value = "run-id"

        good_listing = ListingRecord(
            title="Good Listing",
            source_portal="portal-cb-001",
            source_listing_id="GOOD-001",
            language="en",
        )
        bad_listing = ListingRecord(
            title="Bad Listing",
            source_portal="portal-cb-001",
            source_listing_id="BAD-001",
            language="en",
        )
        mock_scrape.return_value = ([good_listing, bad_listing], False)

        def validate_side_effect(record):
            if record.source_listing_id == "BAD-001":
                raise ValueError("Missing title")
            return record

        mock_validate.side_effect = validate_side_effect
        mock_embed.return_value = [good_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        result = asyncio.get_event_loop().run_until_complete(
            process_portal(mock_conn, canadabuys_portal)
        )

        # Only good listing should be embedded
        assert len(mock_embed.call_args[0][0]) == 1


# ---------------------------------------------------------------------------
# run_pipeline tests
# ---------------------------------------------------------------------------


class TestRunPipeline:
    @patch(
        "scraper.pipeline.orchestrator.is_scraping_allowed_by_robots",
        return_value=True,
    )
    @patch(
        "scraper.pipeline.orchestrator.deduplicate_cross_portal_listings",
        return_value=0,
    )
    @patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
    @patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
    @patch("scraper.pipeline.orchestrator.process_portal", new_callable=AsyncMock)
    @patch("scraper.pipeline.orchestrator.get_enabled_portals")
    @patch("scraper.pipeline.orchestrator.db_connection")
    def test_run_pipeline_processes_all_enabled(
        self,
        mock_db_ctx,
        mock_get_portals,
        mock_process,
        mock_load_kw,
        mock_load_kw_cat,
        mock_cross_portal_dedup,
        mock_robots_gate,
    ):
        """run_pipeline processes all enabled portals."""
        mock_conn = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        portals = [
            PortalRecord(
                id=f"p{i}",
                name=f"Portal{i}",
                url=f"https://portal{i}.example.com",
                level="municipal",
                language="en",
                requires_login=False,
                enabled=True,
            )
            for i in range(3)
        ]
        mock_get_portals.return_value = portals
        mock_process.return_value = {"found": 5, "new": 3, "updated": 2}

        result = asyncio.get_event_loop().run_until_complete(run_pipeline())

        assert mock_process.call_count == 3
        assert len(result) == 3
        assert "Portal0" in result
        assert "Portal1" in result
        assert "Portal2" in result
        mock_cross_portal_dedup.assert_called_once_with(mock_conn)
        assert mock_robots_gate.call_count == 3

    @patch(
        "scraper.pipeline.orchestrator.is_scraping_allowed_by_robots",
        return_value=True,
    )
    @patch(
        "scraper.pipeline.orchestrator.deduplicate_cross_portal_listings",
        return_value=0,
    )
    @patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
    @patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
    @patch("scraper.pipeline.orchestrator.process_portal", new_callable=AsyncMock)
    @patch("scraper.pipeline.orchestrator.get_portal_by_name")
    @patch("scraper.pipeline.orchestrator.db_connection")
    def test_run_pipeline_single_portal(
        self,
        mock_db_ctx,
        mock_get_portal,
        mock_process,
        mock_load_kw,
        mock_load_kw_cat,
        mock_cross_portal_dedup,
        mock_robots_gate,
    ):
        """run_pipeline with portal_name runs only that portal."""
        mock_conn = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        portal = PortalRecord(
            id="p1",
            name="CanadaBuys",
            url="https://canadabuys.canada.ca",
            level="federal",
            language="both",
            requires_login=False,
            enabled=True,
        )
        mock_get_portal.return_value = portal
        mock_process.return_value = {"found": 100, "new": 50, "updated": 50}

        result = asyncio.get_event_loop().run_until_complete(
            run_pipeline(portal_name="CanadaBuys")
        )

        mock_process.assert_called_once_with(
            mock_conn, portal, keywords=["test"],
            keywords_by_category={"Cat": {"EN": ["test"]}},
            skip_embeddings=False,
        )
        assert len(result) == 1
        assert "CanadaBuys" in result
        mock_cross_portal_dedup.assert_called_once_with(mock_conn)
        mock_robots_gate.assert_called_once_with("https://canadabuys.canada.ca")

    @patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
    @patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
    @patch("scraper.pipeline.orchestrator.get_portal_by_name")
    @patch("scraper.pipeline.orchestrator.db_connection")
    def test_run_pipeline_unknown_portal_raises(
        self, mock_db_ctx, mock_get_portal, mock_load_kw, mock_load_kw_cat
    ):
        """run_pipeline raises ValueError for unknown portal name."""
        mock_conn = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_portal.return_value = None

        with pytest.raises(ValueError, match="Portal not found"):
            asyncio.get_event_loop().run_until_complete(
                run_pipeline(portal_name="NonExistent")
            )

    @patch(
        "scraper.pipeline.orchestrator.is_scraping_allowed_by_robots",
        return_value=True,
    )
    @patch(
        "scraper.pipeline.orchestrator.deduplicate_cross_portal_listings",
        return_value=0,
    )
    @patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
    @patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
    @patch("scraper.pipeline.orchestrator.process_portal", new_callable=AsyncMock)
    @patch("scraper.pipeline.orchestrator.get_enabled_portals")
    @patch("scraper.pipeline.orchestrator.db_connection")
    def test_run_pipeline_error_isolation(
        self,
        mock_db_ctx,
        mock_get_portals,
        mock_process,
        mock_load_kw,
        mock_load_kw_cat,
        mock_cross_portal_dedup,
        mock_robots_gate,
    ):
        """A failed portal does not prevent other portals from processing."""
        mock_conn = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        portals = [
            PortalRecord(
                id="p1",
                name="FailPortal",
                url="https://fail.example.com",
                level="municipal",
                language="en",
                requires_login=False,
                enabled=True,
            ),
            PortalRecord(
                id="p2",
                name="GoodPortal",
                url="https://good.example.com",
                level="municipal",
                language="en",
                requires_login=False,
                enabled=True,
            ),
        ]
        mock_get_portals.return_value = portals

        # process_portal handles errors internally and returns error stats
        mock_process.side_effect = [
            {"found": 0, "new": 0, "updated": 0, "error": "Network error"},
            {"found": 10, "new": 5, "updated": 5},
        ]

        result = asyncio.get_event_loop().run_until_complete(run_pipeline())

        assert mock_process.call_count == 2
        assert "error" in result["FailPortal"]
        assert result["GoodPortal"]["found"] == 10
        mock_cross_portal_dedup.assert_called_once_with(mock_conn)
        assert mock_robots_gate.call_count == 2

    @patch(
        "scraper.pipeline.orchestrator.is_scraping_allowed_by_robots",
        side_effect=[False, True],
    )
    @patch(
        "scraper.pipeline.orchestrator.deduplicate_cross_portal_listings",
        return_value=0,
    )
    @patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
    @patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
    @patch("scraper.pipeline.orchestrator.process_portal", new_callable=AsyncMock)
    @patch("scraper.pipeline.orchestrator.get_enabled_portals")
    @patch("scraper.pipeline.orchestrator.db_connection")
    def test_run_pipeline_skips_portal_disallowed_by_robots(
        self,
        mock_db_ctx,
        mock_get_portals,
        mock_process,
        mock_load_kw,
        mock_load_kw_cat,
        mock_cross_portal_dedup,
        mock_robots_gate,
    ):
        """Portals blocked by robots.txt are skipped and not scraped."""
        mock_conn = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        blocked_portal = PortalRecord(
            id="p1",
            name="BlockedPortal",
            url="https://blocked.example.com/private/listings",
            level="municipal",
            language="en",
            requires_login=False,
            enabled=True,
        )
        allowed_portal = PortalRecord(
            id="p2",
            name="AllowedPortal",
            url="https://allowed.example.com/opportunities",
            level="municipal",
            language="en",
            requires_login=False,
            enabled=True,
        )
        mock_get_portals.return_value = [blocked_portal, allowed_portal]
        mock_process.return_value = {"found": 4, "new": 2, "updated": 2}

        result = asyncio.get_event_loop().run_until_complete(run_pipeline())

        mock_process.assert_called_once_with(
            mock_conn,
            allowed_portal,
            keywords=["test"],
            keywords_by_category={"Cat": {"EN": ["test"]}},
            skip_embeddings=False,
        )
        assert result["BlockedPortal"]["skipped"] == "robots_txt_disallow"
        assert result["AllowedPortal"]["found"] == 4
        assert mock_robots_gate.call_count == 2
        mock_cross_portal_dedup.assert_called_once_with(mock_conn)

    @patch("scraper.pipeline.robots.urlopen", side_effect=TimeoutError("timeout"))
    @patch(
        "scraper.pipeline.orchestrator.deduplicate_cross_portal_listings",
        return_value=0,
    )
    @patch("scraper.pipeline.orchestrator.load_keywords_by_category", return_value={"Cat": {"EN": ["test"]}})
    @patch("scraper.pipeline.orchestrator.load_keywords", return_value=["test"])
    @patch("scraper.pipeline.orchestrator.process_portal", new_callable=AsyncMock)
    @patch("scraper.pipeline.orchestrator.get_enabled_portals")
    @patch("scraper.pipeline.orchestrator.db_connection")
    def test_run_pipeline_robots_check_error_fails_open(
        self,
        mock_db_ctx,
        mock_get_portals,
        mock_process,
        mock_load_kw,
        mock_load_kw_cat,
        mock_cross_portal_dedup,
        mock_urlopen,
        caplog,
    ):
        """robots.txt fetch errors still allow processing (fail-open)."""
        caplog.set_level("WARNING", logger="scraper.robots")

        mock_conn = MagicMock()
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        portal = PortalRecord(
            id="p1",
            name="FailOpenPortal",
            url="https://fail-open.example.com/opportunities",
            level="municipal",
            language="en",
            requires_login=False,
            enabled=True,
        )
        mock_get_portals.return_value = [portal]
        mock_process.return_value = {"found": 1, "new": 1, "updated": 0}

        result = asyncio.get_event_loop().run_until_complete(run_pipeline())

        mock_process.assert_called_once()
        assert result["FailOpenPortal"]["found"] == 1
        assert "Allowed due to robots.txt check error (fail-open)" in caplog.text
        mock_cross_portal_dedup.assert_called_once_with(mock_conn)


# ---------------------------------------------------------------------------
# search_used filter logic tests
# ---------------------------------------------------------------------------


class TestSearchUsedFilterLogic:
    """Tests for conditional keyword filtering based on search_used flag."""

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch("scraper.pipeline.orchestrator.deduplicate_listings")
    @patch("scraper.pipeline.orchestrator.filter_listings")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_search_used_true_still_applies_keyword_filter(
        self,
        mock_scrape,
        mock_filter,
        mock_dedup,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        bidsandtenders_portal,
    ):
        """When search_used=True, keyword filter still runs to validate results."""
        mock_start.return_value = "run-id"
        test_listing = ListingRecord(
            title="Translation Services",
            source_portal="portal-bt-001",
            source_listing_id="BT-001",
            language="en",
        )
        mock_scrape.return_value = ([test_listing], True)
        mock_filter.return_value = [test_listing]
        mock_dedup.return_value = [test_listing]
        mock_validate.return_value = test_listing
        mock_embed.return_value = [test_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(
                mock_conn,
                bidsandtenders_portal,
                keywords=["translation"],
                keywords_by_category={"Cat": {"EN": ["translation"]}},
            )
        )

        mock_filter.assert_called_once()

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch("scraper.pipeline.orchestrator.deduplicate_listings")
    @patch("scraper.pipeline.orchestrator.filter_listings")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_search_used_false_applies_keyword_filter(
        self,
        mock_scrape,
        mock_filter,
        mock_dedup,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        bidsandtenders_portal,
    ):
        """When search_used=False (search box not found), filter_listings IS called."""
        mock_start.return_value = "run-id"
        test_listing = ListingRecord(
            title="Translation Services",
            source_portal="portal-bt-001",
            source_listing_id="BT-001",
            language="en",
        )
        mock_scrape.return_value = ([test_listing], False)
        mock_filter.return_value = [test_listing]
        mock_dedup.return_value = [test_listing]
        mock_validate.return_value = test_listing
        mock_embed.return_value = [test_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(
                mock_conn,
                bidsandtenders_portal,
                keywords=["translation"],
                keywords_by_category={"Cat": {"EN": ["translation"]}},
            )
        )

        mock_filter.assert_called_once()

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch("scraper.pipeline.orchestrator.deduplicate_listings")
    @patch("scraper.pipeline.orchestrator.filter_listings")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_non_bidsandtenders_still_filters(
        self,
        mock_scrape,
        mock_filter,
        mock_dedup,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        generic_portal,
    ):
        """Non-BidsAndTenders portals always apply keyword filtering."""
        mock_start.return_value = "run-id"
        test_listing = ListingRecord(
            title="Translation Services",
            source_portal="portal-gen-001",
            source_listing_id="GEN-001",
            language="en",
        )
        mock_scrape.return_value = ([test_listing], False)
        mock_filter.return_value = [test_listing]
        mock_dedup.return_value = [test_listing]
        mock_validate.return_value = test_listing
        mock_embed.return_value = [test_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(
                mock_conn,
                generic_portal,
                keywords=["translation"],
            )
        )

        mock_filter.assert_called_once()

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch("scraper.pipeline.orchestrator.deduplicate_listings")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_all_portals_still_deduplicate(
        self,
        mock_scrape,
        mock_dedup,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        bidsandtenders_portal,
    ):
        """Deduplication runs for all portal types regardless of search_used."""
        mock_start.return_value = "run-id"
        listing1 = ListingRecord(
            title="Listing A",
            source_portal="portal-bt-001",
            source_listing_id="DUP-001",
            language="en",
        )
        listing2 = ListingRecord(
            title="Listing A (dup)",
            source_portal="portal-bt-001",
            source_listing_id="DUP-001",
            language="en",
        )
        mock_scrape.return_value = ([listing1, listing2], True)
        mock_dedup.return_value = [listing1]
        mock_validate.return_value = listing1
        mock_embed.return_value = [listing1]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(
                mock_conn,
                bidsandtenders_portal,
                keywords=["listing"],
                keywords_by_category={"Cat": {"EN": ["listing"]}},
            )
        )

        mock_dedup.assert_called_once()

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch("scraper.pipeline.orchestrator.deduplicate_listings")
    @patch("scraper.pipeline.orchestrator.filter_listings")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_browser_search_used_true_still_applies_keyword_filter(
        self,
        mock_scrape,
        mock_filter,
        mock_dedup,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        generic_portal,
    ):
        """When browser search_used=True, keyword filter still runs to validate results."""
        mock_start.return_value = "run-id"
        test_listing = ListingRecord(
            title="Translation Services",
            source_portal="portal-gen-001",
            source_listing_id="GEN-001",
            language="en",
        )
        mock_scrape.return_value = ([test_listing], True)
        mock_filter.return_value = [test_listing]
        mock_dedup.return_value = [test_listing]
        mock_validate.return_value = test_listing
        mock_embed.return_value = [test_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(
                mock_conn, generic_portal,
                keywords=["translation"],
                keywords_by_category={"Cat": {"EN": ["translation"]}},
            )
        )

        mock_filter.assert_called_once()

    @patch("scraper.pipeline.orchestrator.complete_run")
    @patch("scraper.pipeline.orchestrator.fail_run")
    @patch("scraper.pipeline.orchestrator.start_run")
    @patch("scraper.pipeline.orchestrator.upsert_listings")
    @patch("scraper.pipeline.orchestrator.generate_embeddings")
    @patch("scraper.pipeline.orchestrator.validate_and_score")
    @patch("scraper.pipeline.orchestrator.deduplicate_listings")
    @patch("scraper.pipeline.orchestrator.filter_listings")
    @patch(
        "scraper.pipeline.orchestrator.scrape_portal",
        new_callable=AsyncMock,
    )
    def test_browser_search_used_false_applies_keyword_filter(
        self,
        mock_scrape,
        mock_filter,
        mock_dedup,
        mock_validate,
        mock_embed,
        mock_upsert,
        mock_start,
        mock_fail,
        mock_complete,
        mock_conn,
        generic_portal,
    ):
        """When browser search_used=False, keyword filter IS applied."""
        mock_start.return_value = "run-id"
        test_listing = ListingRecord(
            title="Translation Services",
            source_portal="portal-gen-001",
            source_listing_id="GEN-001",
            language="en",
        )
        mock_scrape.return_value = ([test_listing], False)
        mock_filter.return_value = [test_listing]
        mock_dedup.return_value = [test_listing]
        mock_validate.return_value = test_listing
        mock_embed.return_value = [test_listing]
        mock_upsert.return_value = {"found": 1, "new": 1, "updated": 0}

        asyncio.get_event_loop().run_until_complete(
            process_portal(
                mock_conn, generic_portal,
                keywords=["translation"],
                keywords_by_category={"Cat": {"EN": ["translation"]}},
            )
        )

        mock_filter.assert_called_once()
