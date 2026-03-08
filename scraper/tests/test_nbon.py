"""Tests for NBON scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.nbon import _rows_to_listings, nbon_scrape


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="NBON",
        url="https://nbon-rpanb.gnb.ca/",
        level="provincial",
        province="New Brunswick",
        language="both",
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


class TestNbonHelpers:
    def test_rows_to_listings(self):
        rows = [
            {
                "title": "Supply of Winter Road Salt",
                "reference number": "NB-2026-015",
                "category": "Goods",
                "closing date": "Mar 31, 2026",
                "href": "/opportunity/15",
            }
        ]

        listings = _rows_to_listings(rows, "https://nbon-rpanb.gnb.ca/")

        assert len(listings) == 1
        assert listings[0].reference_number == "NB-2026-015"
        assert listings[0].closing_date == "2026-03-31"
        assert listings[0].source_url == "https://nbon-rpanb.gnb.ca/opportunity/15"


class TestNbonScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.nbon.async_playwright")
    async def test_nbon_scrape(self, mock_pw_func):
        portal = _make_portal()

        listing_frame = AsyncMock()
        listing_frame.url = "https://nbon-rpanb.gnb.ca/listings"
        listing_frame.evaluate = AsyncMock(
            return_value=[
                {
                    "title": "Supply of Winter Road Salt",
                    "reference number": "NB-2026-015",
                    "category": "Goods",
                    "closing date": "Mar 31, 2026",
                    "href": "/opportunity/15",
                }
            ]
        )

        main_frame = AsyncMock()
        main_frame.url = portal.url
        main_frame.evaluate = AsyncMock(return_value=[])

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.url = portal.url
        page.main_frame = main_frame
        page.frames = [main_frame, listing_frame]

        _setup_playwright_mock(mock_pw_func, page)

        result = await nbon_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "NB-2026-015"
        main_frame.evaluate.assert_not_called()

    @pytest.mark.asyncio
    @patch("scraper.pipeline.nbon.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await nbon_scrape(portal)
        assert result == []
