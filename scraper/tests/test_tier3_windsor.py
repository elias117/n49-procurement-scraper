"""Tests for Windsor Tier 3 scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.tier3.windsor import _extract_windsor_listings, windsor_scrape


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="Windsor",
        url="https://opendata.citywindsor.ca/Tools/BidsAndTenders",
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


SAMPLE_WINDSOR_HTML = """
<table>
  <tbody id="tableBody">
    <tr class="BT_BidAndTender Consulting">
      <td>
        <span class="h5">15-26, Engineering Consulting Services</span>
        <div class="BT_BidAndTenderInfo">
          <strong>Open:</strong> <span>Mar 04, 2026 12:00 AM EST</span>
          <strong>Close:</strong> <span>Mar 27, 2026 11:30 AM EST</span>
        </div>
        <div class="BT_TenderDetails"><a href="/Tools/DownloadTender/%7BED9EC5BF-C1AC-415F-8061-1BF13D4375C2%7D">Doc</a></div>
      </td>
    </tr>
  </tbody>
</table>
"""


class TestWindsorParsing:
    def test_extract_windsor_listings(self):
        listings = _extract_windsor_listings(
            SAMPLE_WINDSOR_HTML,
            "https://opendata.citywindsor.ca/Tools/BidsAndTenders",
        )

        assert len(listings) == 1
        listing = listings[0]

        assert listing.title == "15-26, Engineering Consulting Services"
        assert listing.posting_date == "2026-03-04"
        assert listing.closing_date == "2026-03-27"
        assert listing.description and "Consulting" in listing.description


class TestWindsorScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.windsor.async_playwright")
    async def test_windsor_scrape(self, mock_pw_func):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value=SAMPLE_WINDSOR_HTML)
        page.url = portal.url

        _setup_playwright_mock(mock_pw_func, page)

        result = await windsor_scrape(portal)

        assert len(result) == 1
        assert result[0].closing_date == "2026-03-27"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.windsor.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await windsor_scrape(portal)
        assert result == []
