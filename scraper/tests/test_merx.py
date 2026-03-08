"""Tests for MERX scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.merx import (
    _extract_current_page_listings,
    _extract_pagination_urls,
    merx_scrape,
)


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="Ottawa MERX",
        url="https://www.merx.com/cityofottawa",
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

    return mock_browser, mock_context, mock_pw


SAMPLE_MERX_HTML = """
<table>
  <tbody>
    <tr class="mets-table-row odd">
      <td class="mainCol">
        <div class="sol-info-container">
          <div class="sol-title">
            <a class="solicitation-link" href="/cityofottawa/solicitations/open-bids/example/0000316538">PWD/TS Pavement Marking Removal Services</a>
          </div>
          <div class="sol-num">CP-2026-001</div>
          <div class="sol-buyer-name">City of Ottawa</div>
          <span class="sol-publication-date"><span class="date-value">2026/03/06</span></span>
          <span class="sol-closing-date"><span class="date-value">2026/03/20</span></span>
        </div>
      </td>
    </tr>
  </tbody>
</table>
<select id="pagination_select_g_5">
  <option data-href="/cityofottawa/solicitations/open-bids?pageNumber=1">1</option>
  <option data-href="/cityofottawa/solicitations/open-bids?pageNumber=2">2</option>
</select>
"""


class TestMerxParsing:
    def test_extract_current_page_listings_maps_core_fields(self):
        listings = _extract_current_page_listings(
            SAMPLE_MERX_HTML,
            "https://www.merx.com/cityofottawa/solicitations/open-bids",
        )

        assert len(listings) == 1
        listing = listings[0]

        assert listing.title == "PWD/TS Pavement Marking Removal Services"
        assert listing.reference_number == "CP-2026-001"
        assert listing.posting_date == "2026-03-06"
        assert listing.closing_date == "2026-03-20"
        assert listing.source_url == "https://www.merx.com/cityofottawa/solicitations/open-bids/example/0000316538"

    def test_extract_pagination_urls(self):
        urls = _extract_pagination_urls(
            SAMPLE_MERX_HTML,
            "https://www.merx.com/cityofottawa/solicitations/open-bids",
        )

        assert urls == [
            "https://www.merx.com/cityofottawa/solicitations/open-bids?pageNumber=1",
            "https://www.merx.com/cityofottawa/solicitations/open-bids?pageNumber=2",
        ]


class TestMerxScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.merx._collect_listing_pages", new_callable=AsyncMock)
    @patch("scraper.pipeline.merx.async_playwright")
    async def test_merx_scrape_with_mocked_playwright(self, mock_pw_func, mock_collect_pages):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value=SAMPLE_MERX_HTML)
        page.url = "https://www.merx.com/cityofottawa/solicitations/open-bids"

        _setup_playwright_mock(mock_pw_func, page)
        mock_collect_pages.return_value = [page.url]

        result = await merx_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "CP-2026-001"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.merx.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await merx_scrape(portal)
        assert result == []
