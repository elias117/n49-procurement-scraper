"""Tests for the BidsAndTenders family scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.bidsandtenders import (
    BidsAndTendersResult,
    _enrich_with_details,
    _is_sparse,
    _merge_detail,
    _parse_bt_date,
    _resolve_url,
    _row_to_listing,
    bidsandtenders_scrape,
)


def _make_portal(name="Test Portal", url="https://example.bidsandtenders.ca"):
    return PortalRecord(
        id=str(uuid.uuid4()),
        name=name,
        url=url,
        level="municipal",
        province="Ontario",
        language="both",
        requires_login=False,
        enabled=True,
    )


def _make_listing(title="Test Listing", source_listing_id=None):
    return ProcurementListing(
        title=title,
        source_listing_id=source_listing_id or str(uuid.uuid4()),
    )


class _MockApiResponse:
    def __init__(self, payload, ok=True, status=200):
        self._payload = payload
        self.ok = ok
        self.status = status

    async def json(self):
        return self._payload


def _setup_playwright_mock(mock_pw_func, page, api_responses):
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=page)
    mock_context.request.post = AsyncMock(side_effect=api_responses)
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_pw.stop = AsyncMock()

    pw_context = MagicMock()
    pw_context.start = AsyncMock(return_value=mock_pw)
    mock_pw_func.return_value = pw_context

    return mock_browser, mock_context, mock_pw


class TestDateParsing:
    def test_parse_ms_epoch_date(self):
        assert _parse_bt_date("/Date(1773252000000)/") == "2026-03-11"

    def test_parse_display_date(self):
        assert _parse_bt_date("Mar 10, 2026 2:00 PM (EST)") == "2026-03-10"


class TestRowMapping:
    def test_row_to_listing_maps_core_fields(self):
        row = {
            "Id": "abc123",
            "Title": "Snow Removal Services",
            "Description": "<p>Seasonal services</p>",
            "Status": "Open",
            "DateClosing": "/Date(1773252000000)/",
            "DateAvailable": "/Date(1772128800000)/",
        }

        listing = _row_to_listing(
            row=row,
            base_url="https://example.bidsandtenders.ca",
            home_path="/Module/Tenders/en",
        )

        assert listing is not None
        assert listing.title == "Snow Removal Services"
        assert listing.source_listing_id == "abc123"
        assert listing.source_url == "https://example.bidsandtenders.ca/Module/Tenders/en/Tender/Detail/abc123"
        assert listing.status == "Open"
        assert listing.posting_date == "2026-02-26"
        assert listing.closing_date == "2026-03-11"


class TestResolveUrl:
    def test_absolute_url_returned_unchanged(self):
        result = _resolve_url(
            "https://example.bidsandtenders.ca/listing/123",
            "https://example.bidsandtenders.ca/",
        )
        assert result == "https://example.bidsandtenders.ca/listing/123"

    def test_relative_url_resolved(self):
        result = _resolve_url(
            "/Module/Tenders/en/Tender/Detail/abc123",
            "https://example.bidsandtenders.ca/",
        )
        assert result == "https://example.bidsandtenders.ca/Module/Tenders/en/Tender/Detail/abc123"


class TestIsSparse:
    def test_sparse_when_description_is_none(self):
        listing = ProcurementListing(title="Test")
        assert _is_sparse(listing) is True

    def test_not_sparse_when_description_and_closing_date_present(self):
        listing = ProcurementListing(
            title="Test",
            description="A sufficiently long description with real details inside",
            closing_date="2026-04-01",
        )
        assert _is_sparse(listing) is False


class TestMergeDetail:
    def test_merge_fills_none_fields(self):
        original = ProcurementListing(
            title="Original Title",
            source_url="https://example.com/listing/1",
        )
        detail = ProcurementListing(
            title="Detail Title",
            description="Full description from detail page",
            closing_date="2026-04-15",
            value_min=50000.0,
            contact_name="Jane Doe",
            contact_email="jane@example.ca",
        )
        merged = _merge_detail(original, detail)

        assert merged.title == "Original Title"
        assert merged.description == "Full description from detail page"
        assert merged.closing_date == "2026-04-15"
        assert merged.value_min == 50000.0
        assert merged.contact_name == "Jane Doe"
        assert merged.contact_email == "jane@example.ca"


class TestEnrichWithDetails:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listing_detail")
    async def test_enriches_sparse_listings_with_urls(self, mock_extract_detail):
        portal = _make_portal()
        sparse_listing = ProcurementListing(
            title="Sparse Tender",
            source_url="https://example.bidsandtenders.ca/Tender/Detail/1",
            source_listing_id="SPARSE-1",
        )
        detail_listing = ProcurementListing(
            title="Detail Title",
            description="Full description from detail",
            closing_date="2026-05-01",
            value_min=100000.0,
        )
        mock_extract_detail.return_value = detail_listing

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value="<html>detail</html>")

        result = await _enrich_with_details([sparse_listing], page, portal)

        assert len(result) == 1
        assert result[0].title == "Sparse Tender"
        assert result[0].description == "Full description from detail"
        assert result[0].closing_date == "2026-05-01"
        page.goto.assert_called_once()


class TestBidsAndTendersScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders._enrich_with_details", new_callable=AsyncMock)
    @patch("scraper.pipeline.bidsandtenders._extract_search_metadata", new_callable=AsyncMock)
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_direct_scrape_fetches_all_pages(
        self,
        mock_pw_func,
        mock_extract_metadata,
        mock_enrich,
    ):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.bidsandtenders.ca/Module/Tenders/en"

        mock_extract_metadata.return_value = (
            "/Module/Tenders/en",
            "node-123",
            "token-abc",
        )
        mock_enrich.side_effect = lambda listings, *_: listings

        api_responses = [
            _MockApiResponse(
                {
                    "success": True,
                    "total": 3,
                    "data": [
                        {
                            "Id": "ID-1",
                            "Title": "Tender One",
                            "DateClosing": "/Date(1773252000000)/",
                            "DateAvailable": "/Date(1772128800000)/",
                            "Status": "Open",
                        },
                        {
                            "Id": "ID-2",
                            "Title": "Tender Two",
                            "DateClosing": "/Date(1773338400000)/",
                            "DateAvailable": "/Date(1772128800000)/",
                            "Status": "Open",
                        },
                    ],
                }
            ),
            _MockApiResponse(
                {
                    "success": True,
                    "total": 3,
                    "data": [
                        {
                            "Id": "ID-3",
                            "Title": "Tender Three",
                            "DateClosing": "/Date(1773424800000)/",
                            "DateAvailable": "/Date(1772128800000)/",
                            "Status": "Open",
                        }
                    ],
                }
            ),
        ]

        _, mock_context, _ = _setup_playwright_mock(mock_pw_func, page, api_responses)

        result = await bidsandtenders_scrape(portal, keywords_by_category={"Cat": {"EN": ["x"]}})

        assert isinstance(result, BidsAndTendersResult)
        assert result.search_used is False
        assert len(result.listings) == 3

        assert mock_context.request.post.call_count == 2
        first_call = mock_context.request.post.call_args_list[0]
        params = first_call.kwargs["params"]
        form = first_call.kwargs["form"]
        assert params["status"] == "Open"
        assert form["keywords"] == ""

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders._enrich_with_details", new_callable=AsyncMock)
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders._extract_search_metadata", new_callable=AsyncMock)
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_falls_back_to_html_extract_when_endpoint_unavailable(
        self,
        mock_pw_func,
        mock_extract_metadata,
        mock_extract,
        mock_enrich,
    ):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value="<html>fallback content</html>")
        page.url = "https://example.bidsandtenders.ca/Module/Tenders/en"

        mock_extract_metadata.return_value = None
        mock_extract.return_value = [_make_listing("Fallback Listing", "FB-1")]
        mock_enrich.side_effect = lambda listings, *_: listings

        _setup_playwright_mock(mock_pw_func, page, api_responses=[])

        result = await bidsandtenders_scrape(portal)

        assert len(result.listings) == 1
        assert result.listings[0].title == "Fallback Listing"
        assert result.search_used is False

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await bidsandtenders_scrape(portal)
        assert result.listings == []
        assert result.search_used is False
