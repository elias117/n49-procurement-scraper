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
<div>
  <a class="btn btn-link btn-large btn-link-header" href="https://example.com/event/1">Fire Life Safety System Maintenance Services</a>
  <div class="phx table-row-layout">
    <div class="phx table-cell-layout"><div class="phx data-row-name">Open</div></div>
    <div class="phx table-cell-layout"><div class="phx data-row-content">03/03/2026 3:00 PM PST</div></div>
  </div>
  <div class="phx table-row-layout">
    <div class="phx table-cell-layout"><div class="phx data-row-name">Close</div></div>
    <div class="phx table-cell-layout"><div class="phx data-row-content">07/04/2026 3:00 PM PDT</div></div>
  </div>
  <div class="phx table-row-layout">
    <div class="phx table-cell-layout"><div class="phx data-row-name">Type</div></div>
    <div class="phx table-cell-layout"><div class="phx data-row-content">RFP</div></div>
  </div>
  <div class="phx table-row-layout">
    <div class="phx table-cell-layout"><div class="phx data-row-name">Number</div></div>
    <div class="phx table-cell-layout"><div class="phx data-row-content">PS20251541-REFM-RFP</div></div>
  </div>
</div>
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
        assert listing.source_url == "https://example.com/event/1"


class TestVancouverScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.vancouver.async_playwright")
    async def test_vancouver_scrape(self, mock_pw_func):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
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
