"""Tests for SEAO scraper."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord
from scraper.pipeline.seao import (
    SEAO_RESULTS_URL,
    _build_listing_from_row,
    _header_index_map,
    seao_scrape,
)


def _make_portal():
    return PortalRecord(
        id=str(uuid.uuid4()),
        name="SEAO Quebec",
        url="https://seao.gouv.qc.ca/avis-resultat-recherche",
        level="provincial",
        province="Quebec",
        language="fr",
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


class TestSeaoParsingHelpers:
    def test_header_index_map_handles_french_headers(self):
        headers = [
            "Titre",
            "Numéro de référence",
            "Organisme",
            "Catégorie",
            "Date d'ouverture",
            "Date de fermeture",
        ]

        result = _header_index_map(headers)

        assert result["title"] == 0
        assert result["reference_number"] == 1
        assert result["organization"] == 2
        assert result["category"] == 3
        assert result["open_date"] == 4
        assert result["close_date"] == 5

    def test_build_listing_from_row_maps_expected_fields(self):
        headers = [
            "Titre",
            "Numéro de référence",
            "Organisme",
            "Catégorie",
            "Date d'ouverture",
            "Date de fermeture",
        ]
        row = {
            "cells": [
                "Appel d'offres déneigement",
                "SEAO-2026-001",
                "Ville de Québec",
                "Travaux publics",
                "01/03/2026",
                "15/03/2026",
            ],
            "href": "/avis-resultat-recherche/consulter/ABC123",
            "anchor_text": "Appel d'offres déneigement",
        }

        listing = _build_listing_from_row(headers, row, SEAO_RESULTS_URL)

        assert listing is not None
        assert listing.title == "Appel d'offres déneigement"
        assert listing.reference_number == "SEAO-2026-001"
        assert listing.posting_date == "2026-03-01"
        assert listing.closing_date == "2026-03-15"
        assert listing.source_listing_id == "SEAO-2026-001"
        assert listing.source_url == "https://seao.gouv.qc.ca/avis-resultat-recherche/consulter/ABC123"
        assert listing.raw_location == "Ville de Québec"


class TestSeaoScrape:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.seao._go_to_next_page", new_callable=AsyncMock)
    @patch("scraper.pipeline.seao._extract_current_page_rows", new_callable=AsyncMock)
    @patch("scraper.pipeline.seao.async_playwright")
    async def test_scrape_collects_multiple_pages(
        self,
        mock_pw_func,
        mock_extract_rows,
        mock_next,
    ):
        portal = _make_portal()

        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.url = SEAO_RESULTS_URL

        _setup_playwright_mock(mock_pw_func, page)

        headers = [
            "Titre",
            "Numéro de référence",
            "Organisme",
            "Catégorie",
            "Date d'ouverture",
            "Date de fermeture",
        ]

        mock_extract_rows.side_effect = [
            (
                headers,
                [
                    {
                        "cells": [
                            "Avis 1",
                            "REF-1",
                            "Org 1",
                            "Cat 1",
                            "01/03/2026",
                            "05/03/2026",
                        ],
                        "href": "/avis-resultat-recherche/consulter/1",
                        "anchor_text": "Avis 1",
                    }
                ],
            ),
            (
                headers,
                [
                    {
                        "cells": [
                            "Avis 2",
                            "REF-2",
                            "Org 2",
                            "Cat 2",
                            "02/03/2026",
                            "06/03/2026",
                        ],
                        "href": "/avis-resultat-recherche/consulter/2",
                        "anchor_text": "Avis 2",
                    }
                ],
            ),
        ]
        mock_next.side_effect = [True, False]

        listings = await seao_scrape(portal)

        assert len(listings) == 2
        assert listings[0].reference_number == "REF-1"
        assert listings[1].reference_number == "REF-2"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.seao.async_playwright", None)
    async def test_returns_empty_when_playwright_missing(self):
        portal = _make_portal()
        result = await seao_scrape(portal)
        assert result == []
