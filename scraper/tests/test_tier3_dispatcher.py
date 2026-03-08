"""Tests for Tier 3 dispatcher."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.tier3.dispatcher import classify_tier3_portal, tier3_scrape


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


def test_classify_windsor():
    assert classify_tier3_portal(_portal("Windsor", "https://opendata.citywindsor.ca/Tools/BidsAndTenders")) == "windsor"


def test_classify_vancouver():
    assert classify_tier3_portal(_portal("Vancouver", "https://bids.vancouver.ca/")) == "vancouver"


def test_classify_montreal():
    assert classify_tier3_portal(_portal("Montreal", "https://montreal.ca/en/services/tenders-and-contracts")) == "montreal"


@pytest.mark.asyncio
@patch("scraper.pipeline.tier3.dispatcher.windsor_scrape", new_callable=AsyncMock)
async def test_dispatch_windsor(mock_windsor):
    portal = _portal("Windsor", "https://opendata.citywindsor.ca/Tools/BidsAndTenders")
    listing = ProcurementListing(title="Windsor Listing", source_listing_id="WIN-1")
    mock_windsor.return_value = [listing]

    result = await tier3_scrape(portal)

    assert result == [listing]
    mock_windsor.assert_called_once_with(portal)


@pytest.mark.asyncio
async def test_unknown_tier3_returns_empty():
    portal = _portal("Unknown", "https://example.com/custom")
    result = await tier3_scrape(portal)
    assert result == []
