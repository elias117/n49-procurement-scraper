"""Tests for BC Bid scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.bcbid import _rows_to_listings, bcbid_scrape


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="BC Bid",
        url="https://www.bcbid.gov.bc.ca/",
        level="provincial",
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


class TestBcBidHelpers:
    def test_rows_to_listings(self):
        rows = [
            {
                "title": "IT Infrastructure Upgrade",
                "reference": "BC-2026-001",
                "category": "Services",
                "closing date": "2026-03-31",
                "href": "https://bcbid.gov.bc.ca/opportunity/1",
            }
        ]

        listings = _rows_to_listings(rows, "https://bcbid.gov.bc.ca/")

        assert len(listings) == 1
        assert listings[0].reference_number == "BC-2026-001"
        assert listings[0].closing_date == "2026-03-31"


class TestBcBidScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bcbid.async_playwright")
    async def test_bcbid_scrape(self, mock_pw_func):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.text_content = AsyncMock(return_value="Ready")
        page.evaluate = AsyncMock(
            return_value=[
                {
                    "title": "IT Infrastructure Upgrade",
                    "reference": "BC-2026-001",
                    "category": "Services",
                    "closing date": "2026-03-31",
                    "href": "/opportunity/1",
                }
            ]
        )
        page.url = portal.url

        _setup_playwright_mock(mock_pw_func, page)

        result = await bcbid_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "BC-2026-001"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bcbid.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await bcbid_scrape(portal)
        assert result == []
