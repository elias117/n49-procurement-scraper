"""Tests for Vancouver Tier 3 scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.tier3.vancouver import _extract_vancouver_listings, vancouver_scrape


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="Vancouver",
        url="https://bids.vancouver.ca/",
        level="municipal",
        province="British Columbia",
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


SAMPLE_VANCOUVER_HTML = """
<table class="table phx table-hover no-column-borders">
  <tr>
    <td>Open</td>
    <td>
      <a href="/ViewSourcingEvent?id=1">Fire Life Safety System Maintenance Services</a>
      Open 03/03/2026 3:00 PM
      Close 07/04/2026 3:00 PM
      Type RFP
      Number PS20251541-REFM-RFP
    </td>
  </tr>
</table>
"""


class TestVancouverParsing:
    def test_extract_vancouver_listings(self):
        listings = _extract_vancouver_listings(
            SAMPLE_VANCOUVER_HTML,
            "https://bids.vancouver.ca/",
        )

        assert len(listings) == 1
        listing = listings[0]

        assert listing.title == "Fire Life Safety System Maintenance Services"
        assert listing.reference_number == "PS20251541-REFM-RFP"
        assert listing.closing_date == "2026-04-07"
        assert "ViewSourcingEvent" in listing.source_url


class TestVancouverScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.vancouver._open_vancouver_listings_page")
    @patch("scraper.pipeline.tier3.vancouver.async_playwright")
    async def test_vancouver_scrape(self, mock_pw_func, mock_open_page):
        portal = _make_portal()

        mock_open_page.return_value = "https://bids.sciquest.com/apps/Router/PublicEvent"

        page = AsyncMock()
        page.content = AsyncMock(return_value=SAMPLE_VANCOUVER_HTML)
        page.url = portal.url

        _setup_playwright_mock(mock_pw_func, page)

        result = await vancouver_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "PS20251541-REFM-RFP"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.vancouver.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await vancouver_scrape(portal)
        assert result == []
