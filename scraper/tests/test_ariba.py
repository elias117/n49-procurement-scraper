"""Tests for Ariba scraper family."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.ariba import (
    _extract_ariba_profile_listings,
    _extract_toronto_records,
    _parse_json_from_response_content,
    ariba_scrape,
)


def _portal(name: str, url: str) -> PortalRecord:
    return PortalRecord(
        id=str(uuid.uuid4()),
        name=name,
        url=url,
        level="municipal",
        province="Ontario",
        language="en",
        requires_login=False,
        enabled=True,
    )


def _setup_playwright_mock(mock_pw_func, page):
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_pw.stop = AsyncMock()

    pw_context = MagicMock()
    pw_context.start = AsyncMock(return_value=mock_pw)
    mock_pw_func.return_value = pw_context


ARIBA_PROFILE_HTML = """
<table>
  <tr>
    <td><a class="QuoteSearchResultTitle">938766 - Employee Surveys</a></td>
  </tr>
  <tr>
    <td class="adse-ADQSRR-detail">
      <span>The City of Edmonton</span>
      <span>Posted:</span><span>9 Apr 2025</span>
      <span>Closes:</span><span>31 Oct 2030 3:00 PM PDT</span>
    </td>
  </tr>
  <tr>
    <td class="adse-ADQSRR-topBorderedSection">
      <span>Product and Service Categories:</span>
      <span>Research and consulting services</span>
    </td>
  </tr>
</table>
"""


class TestAribaHelpers:
    def test_parse_json_from_html_wrapped_payload(self):
        wrapped = "<html><body><pre>{\"value\":[{\"id\":\"1\"}]}</pre></body></html>"
        parsed = _parse_json_from_response_content(wrapped)

        assert isinstance(parsed, dict)
        assert parsed["value"][0]["id"] == "1"

    def test_extract_ariba_profile_listings(self):
        listings = _extract_ariba_profile_listings(
            ARIBA_PROFILE_HTML,
            "https://service.ariba.com/Discovery.aw/ad/profile?key=AN01394774623",
        )

        assert len(listings) == 1
        listing = listings[0]

        assert listing.title == "Employee Surveys"
        assert listing.reference_number == "938766"
        assert listing.closing_date == "2030-10-31"

    def test_extract_toronto_records(self):
        records = [
            {
                "id": "abc123",
                "Posting_Title": "Snow Clearing Services",
                "Reference_Number": "DOC-2026-001",
                "High_Level_Category": "General Services",
                "Closing_Date": "2026-03-28",
                "Issue_Date": "2026-03-01",
                "Ariba_Discovery_Posting_Link": "https://portal.us.bn.cloud.ariba.com/dashboard/public/appext/comsapsbncdiscoveryui#/RfxEvent/preview/123",
            }
        ]

        listings = _extract_toronto_records(records, "https://secure.toronto.ca/api")

        assert len(listings) == 1
        listing = listings[0]
        assert listing.reference_number == "DOC-2026-001"
        assert listing.closing_date == "2026-03-28"
        assert listing.source_listing_id == "abc123"


class TestAribaScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.ariba._scrape_edmonton", new_callable=AsyncMock)
    @patch("scraper.pipeline.ariba.async_playwright")
    async def test_ariba_dispatch_edmonton(self, mock_pw_func, mock_edmonton):
        portal = _portal(
            "Edmonton",
            "https://www.edmonton.ca/business_economy/selling_to_the_city/bid-procurement-opportunities",
        )

        page = AsyncMock()
        _setup_playwright_mock(mock_pw_func, page)

        mock_edmonton.return_value = [
            ProcurementListing(title="Test Edmonton Listing", source_listing_id="EDM-1")
        ]

        result = await ariba_scrape(portal)

        assert len(result) == 1
        assert result[0].title == "Test Edmonton Listing"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.ariba.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _portal("Toronto", "https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/")
        result = await ariba_scrape(portal)
        assert result == []
