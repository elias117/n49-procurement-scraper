"""Tests for SaskTenders scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.sasktenders import _extract_sasktenders_listings, sasktenders_scrape


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="SaskTenders",
        url="https://www.sasktenders.ca/",
        level="provincial",
        province="Saskatchewan",
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


SASK_HTML = """
<div class="HeaderAccordionPlusFormat">
  <table class='ContentAccordionFormat'>
    <tr>
      <td></td>
      <td>RFI Transmission Pipeline Transaction Business Solution</td>
      <td>SaskEnergy Incorporated</td>
      <td>TX7254</td>
      <td>Mar 06, 2026<br/>01:15 PM CST</td>
      <td>Mar 27, 2026<br/>05:00 PM CST</td>
      <td>Open</td>
    </tr>
  </table>
</div>
<div class="ContentAccordionFormat_SearchPage" style="display:none;">
  <table>
    <tr><th>Competition Type:</th><td>Request for Information</td></tr>
    <tr><td><a href='print.aspx?competitionId=77d593a3-14f5-422b-bc53-9a68ec2fb077'>Print this Competition</a></td></tr>
  </table>
</div>
"""


class TestSaskTendersParsing:
    def test_extract_sasktenders_listings(self):
        listings = _extract_sasktenders_listings(
            SASK_HTML,
            "https://www.sasktenders.ca/",
        )

        assert len(listings) == 1
        listing = listings[0]

        assert listing.reference_number == "TX7254"
        assert listing.posting_date == "2026-03-06"
        assert listing.closing_date == "2026-03-27"
        assert listing.source_url == "https://www.sasktenders.ca/print.aspx?competitionId=77d593a3-14f5-422b-bc53-9a68ec2fb077"


class TestSaskTendersScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.sasktenders.async_playwright")
    async def test_sasktenders_scrape(self, mock_pw_func):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value=SASK_HTML)
        page.url = portal.url

        _setup_playwright_mock(mock_pw_func, page)

        result = await sasktenders_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "TX7254"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.sasktenders.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await sasktenders_scrape(portal)
        assert result == []
