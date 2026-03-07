"""Tests for Montreal Tier 3 scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.tier3.montreal import (
    _extract_detail_metadata,
    _extract_summary_listings,
    _merge_summary_and_detail,
    montreal_scrape,
)


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="Montreal",
        url="https://montreal.ca/en/services/tenders-and-contracts",
        level="municipal",
        province="Quebec",
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


SUMMARY_HTML = """
<ul class="list-group list-group-teaser">
  <li class="list-group-item list-element p-0">
    <a class="list-group-item-action d-block p-2" href="/avis-dappels-doffres/services-professionnels-pour-la-conception-107529">
      <div class="list-group-item-title">Services professionnels pour la conception et la réalisation de l’exposition Poptopia à la Biosphère</div>
      <ul class="list-group-infos">
        <li class="list-group-info-item">5 mars 2026</li>
        <li class="list-group-info-item">Ville de Montréal</li>
      </ul>
    </a>
  </li>
</ul>
"""

DETAIL_HTML = """
<div class="list-item-icon-content">
  <div class="list-item-icon-label">Date limite de dépôt</div>Mardi 7 avril 2026 avant 14 h 00
</div>
<div class="list-item">
  <div class="list-item-content">
    <div class="list-item-label">Catégorie</div>
    <div class="list-item-content">Services professionnels</div>
  </div>
</div>
<div class="list-item">
  <div class="list-item-content">
    <div class="list-item-label">Numéro d'appel d'offres</div>
    <div class="list-item-content">2026-005-P</div>
  </div>
</div>
<div class="list-item">
  <div class="list-item-content">
    <div class="list-item-label">Date de disponibilité des documents</div>6 mars 2026
  </div>
</div>
"""


class TestMontrealParsing:
    def test_summary_and_detail_merge(self):
        summaries, next_url = _extract_summary_listings(
            SUMMARY_HTML,
            "https://montreal.ca/avis-dappel-doffres",
        )

        assert len(summaries) == 1
        assert next_url is None

        metadata = _extract_detail_metadata(DETAIL_HTML)
        merged = _merge_summary_and_detail(summaries[0], metadata)

        assert merged.reference_number == "2026-005-P"
        assert merged.closing_date == "2026-04-07"
        assert merged.posting_date == "2026-03-06"
        assert merged.description and "Services professionnels" in merged.description


class TestMontrealScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.montreal.async_playwright")
    async def test_montreal_scrape(self, mock_pw_func):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(side_effect=[SUMMARY_HTML, DETAIL_HTML])
        page.url = "https://montreal.ca/avis-dappel-doffres"

        _setup_playwright_mock(mock_pw_func, page)

        result = await montreal_scrape(portal)

        assert len(result) == 1
        assert result[0].reference_number == "2026-005-P"
        assert result[0].closing_date == "2026-04-07"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.tier3.montreal.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await montreal_scrape(portal)
        assert result == []
