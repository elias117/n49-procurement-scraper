"""Tests for APC scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.apc import _rows_to_listings, apc_scrape


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="APC",
        url="https://vendor.purchasingconnection.ca/",
        level="provincial",
        province="Alberta",
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


class TestApcHelpers:
    def test_rows_to_listings(self):
        rows = [
            {
                "title": "Supply of Safety Equipment",
                "reference_number": "APC-001",
                "category": "Goods",
                "closing_date": "2026-03-20",
                "source_url": "https://vendor.purchasingconnection.ca/opportunity/1",
            }
        ]

        listings = _rows_to_listings(rows, "https://vendor.purchasingconnection.ca/")

        assert len(listings) == 1
        assert listings[0].reference_number == "APC-001"
        assert listings[0].closing_date == "2026-03-20"


class TestApcScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.apc.async_playwright")
    async def test_apc_scrape(self, mock_pw_func):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock(
            return_value=[
                {
                    "title": "Supply of Safety Equipment",
                    "reference_number": "APC-001",
                    "category": "Goods",
                    "closing_date": "2026-03-20",
                    "source_url": "/opportunity/1",
                }
            ]
        )
        page.url = portal.url

        _setup_playwright_mock(mock_pw_func, page)

        result = await apc_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "APC-001"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.apc.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await apc_scrape(portal)
        assert result == []
