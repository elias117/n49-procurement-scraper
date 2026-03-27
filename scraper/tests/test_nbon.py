"""Tests for NBON scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.nbon import _to_listing, nbon_scrape


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
    def test_to_listing_valid_row(self):
        row = {
            "title": "Supply of Winter Road Salt",
            "reference_number": "NB-2026-015",
            "organization": "Dept of Transportation",
            "closing_date": "2026/03/31 14:00",
            "posting_date": "2026/02/01 09:00",
            "href": "javascript:openWindow('showDisplayDocument?id=15')",
        }

        listing = _to_listing(row, "https://nbon-rpanb.gnb.ca/")

        assert listing is not None
        assert listing.reference_number == "NB-2026-015"
        assert listing.closing_date == "2026-03-31"
        assert "showDisplayDocument" in listing.source_url

    def test_to_listing_returns_none_without_title(self):
        row = {"title": None, "reference_number": None}
        assert _to_listing(row, "https://nbon-rpanb.gnb.ca/") is None


class TestNbonScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.nbon._extract_open_rows")
    @patch("scraper.pipeline.nbon._open_opportunity_frame")
    @patch("scraper.pipeline.nbon._ensure_nbon_home")
    @patch("scraper.pipeline.nbon.async_playwright")
    async def test_nbon_scrape(self, mock_pw_func, mock_ensure, mock_open_frame, mock_extract):
        portal = _make_portal()

        # Mock the frame returned by _open_opportunity_frame
        frame = MagicMock()
        frame.url = "https://nbon-rpanb.gnb.ca/listings"
        mock_open_frame.return_value = frame

        # Mock extracted rows
        mock_extract.return_value = [
            {
                "title": "Supply of Winter Road Salt",
                "reference_number": "NB-2026-015",
                "organization": "Dept of Transportation",
                "posting_date": "2026/02/01 09:00",
                "closing_date": "2026/03/31 14:00",
                "href": "javascript:openWindow('showDisplayDocument?id=15')",
            }
        ]

        page = AsyncMock()
        _setup_playwright_mock(mock_pw_func, page)

        result = await nbon_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "NB-2026-015"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.nbon._open_opportunity_frame")
    @patch("scraper.pipeline.nbon._ensure_nbon_home")
    @patch("scraper.pipeline.nbon.async_playwright")
    async def test_nbon_scrape_no_frame(self, mock_pw_func, mock_ensure, mock_open_frame):
        """Returns empty when no opportunity frame is found."""
        portal = _make_portal()
        mock_open_frame.return_value = None

        page = AsyncMock()
        _setup_playwright_mock(mock_pw_func, page)

        result = await nbon_scrape(portal)
        assert result == []

    @pytest.mark.asyncio
    @patch("scraper.pipeline.nbon.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await nbon_scrape(portal)
        assert result == []
