"""
Tests for the BidsAndTenders platform scraper.

All Playwright interactions are mocked. Tests cover:
- Search input discovery (_find_search_input)
- Search execution (_execute_search)
- Keyword search with OR queries and fallback
- Search box not found fallback
- Function signature and return type
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.bidsandtenders import (
    BidsAndTendersResult,
    _find_search_input,
    _execute_search,
    _reset_search,
    bidsandtenders_scrape,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_portal(name="Test Portal", url="https://example.bidsandtenders.ca"):
    """Create a minimal PortalRecord for testing."""
    return PortalRecord(
        id=str(uuid.uuid4()),
        name=name,
        url=url,
        level="municipal",
        province="Ontario",
        language="both",
        requires_login=False,
        enabled=True,
    )


def _make_listing(title="Test Listing", source_listing_id=None):
    """Create a minimal ProcurementListing for testing."""
    return ProcurementListing(
        title=title,
        source_listing_id=source_listing_id or str(uuid.uuid4()),
    )


def _make_mock_locator(visible=True):
    """Create a mock Playwright locator."""
    locator = AsyncMock()
    locator.is_visible = AsyncMock(return_value=visible)
    locator.fill = AsyncMock()
    locator.press = AsyncMock()
    locator.click = AsyncMock()
    return locator


def _make_mock_page(
    searchbox_visible=True,
    placeholder_visible=False,
    input_text_visible=False,
    html_content="<html><body>test</body></html>",
):
    """Create a mock Playwright page with configurable search input visibility."""
    page = AsyncMock()

    # Mock locators for search input discovery
    searchbox_locator = _make_mock_locator(visible=searchbox_visible)
    placeholder_locator = _make_mock_locator(visible=placeholder_visible)
    input_text_locator = _make_mock_locator(visible=input_text_visible)

    page.get_by_role = MagicMock(return_value=searchbox_locator)
    page.get_by_placeholder = MagicMock(return_value=placeholder_locator)

    # Mock locator().first chain
    locator_chain = MagicMock()
    locator_chain.first = input_text_locator
    page.locator = MagicMock(return_value=locator_chain)

    # Mock page methods
    page.content = AsyncMock(return_value=html_content)
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    # Mock get_by_text for reset button and limit option
    reset_locator = _make_mock_locator(visible=True)
    page.get_by_text = MagicMock(return_value=reset_locator)

    # Store locators for assertion access
    page._searchbox_locator = searchbox_locator
    page._placeholder_locator = placeholder_locator
    page._input_text_locator = input_text_locator
    page._reset_locator = reset_locator

    return page


def _setup_playwright_mock(mock_pw_func, page):
    """
    Configure mock async_playwright to return a properly chained mock.

    Production code calls: p = await async_playwright().start()
    So async_playwright() is sync -> returns context manager with async .start()
    """
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_pw.stop = AsyncMock()

    # async_playwright() returns an object with async .start()
    pw_context = MagicMock()
    pw_context.start = AsyncMock(return_value=mock_pw)
    mock_pw_func.return_value = pw_context

    return mock_browser, mock_context, mock_pw


def _sample_keywords_by_category():
    """Create a sample keywords_by_category dict for testing."""
    return {
        "Category A": {
            "EN": ["keyword-a-en-1", "keyword-a-en-2", "keyword-a-en-3"],
            "FR": ["keyword-a-fr-1", "keyword-a-fr-2", "keyword-a-fr-3"],
        },
        "Category B": {
            "EN": ["keyword-b-en-1", "keyword-b-en-2"],
            "FR": ["keyword-b-fr-1", "keyword-b-fr-2"],
        },
    }


# ---------------------------------------------------------------------------
# TestFindSearchInput
# ---------------------------------------------------------------------------


class TestFindSearchInput:
    @pytest.mark.asyncio
    async def test_finds_by_role(self):
        page = _make_mock_page(searchbox_visible=True)
        result = await _find_search_input(page)
        assert result is not None
        assert result is page._searchbox_locator

    @pytest.mark.asyncio
    async def test_falls_back_to_placeholder(self):
        page = _make_mock_page(
            searchbox_visible=False, placeholder_visible=True
        )
        result = await _find_search_input(page)
        assert result is not None
        assert result is page._placeholder_locator

    @pytest.mark.asyncio
    async def test_falls_back_to_input_type(self):
        page = _make_mock_page(
            searchbox_visible=False,
            placeholder_visible=False,
            input_text_visible=True,
        )
        result = await _find_search_input(page)
        assert result is not None
        assert result is page._input_text_locator

    @pytest.mark.asyncio
    async def test_returns_none_when_nothing_found(self):
        page = _make_mock_page(
            searchbox_visible=False,
            placeholder_visible=False,
            input_text_visible=False,
        )
        result = await _find_search_input(page)
        assert result is None


# ---------------------------------------------------------------------------
# TestExecuteSearch
# ---------------------------------------------------------------------------


class TestExecuteSearch:
    @pytest.mark.asyncio
    async def test_fills_and_presses_enter(self):
        page = _make_mock_page()
        search_input = _make_mock_locator()
        await _execute_search(page, search_input, "translation OR traduction")
        search_input.fill.assert_any_call("")
        search_input.fill.assert_any_call("translation OR traduction")
        search_input.press.assert_called_once_with("Enter")

    @pytest.mark.asyncio
    async def test_waits_for_networkidle(self):
        page = _make_mock_page()
        search_input = _make_mock_locator()
        await _execute_search(page, search_input, "test")
        page.wait_for_load_state.assert_called_with("networkidle")

    @pytest.mark.asyncio
    async def test_returns_page_content(self):
        page = _make_mock_page(html_content="<html>search results</html>")
        search_input = _make_mock_locator()
        result = await _execute_search(page, search_input, "test")
        assert result == "<html>search results</html>"


# ---------------------------------------------------------------------------
# TestKeywordSearch (integration-level, mocked Playwright)
# ---------------------------------------------------------------------------


class TestKeywordSearch:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_or_query_constructed_correctly(
        self, mock_pw_func, mock_extract
    ):
        """Verify the OR-joined query is typed into the search box."""
        portal = _make_portal()
        listings = [_make_listing(f"L{i}", f"ID-{i}") for i in range(3)]
        mock_extract.return_value = listings

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        keywords = {
            "Cat1": {
                "EN": ["term1", "term2"],
                "FR": ["terme1", "terme2"],
            }
        }

        result = await bidsandtenders_scrape(portal, keywords)

        # Check that fill was called with an OR-joined query
        fill_calls = page._searchbox_locator.fill.call_args_list
        query_calls = [
            c for c in fill_calls if c[0][0] and " OR " in str(c[0][0])
        ]
        assert len(query_calls) >= 1
        query_text = query_calls[0][0][0]
        assert " OR " in query_text

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_multiple_categories_searched(
        self, mock_pw_func, mock_extract
    ):
        """Verify each category triggers a search."""
        portal = _make_portal()
        mock_extract.return_value = [_make_listing("L1", "ID-1")]

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        keywords = {
            "Cat1": {"EN": ["term1"], "FR": ["terme1"]},
            "Cat2": {"EN": ["term2"], "FR": ["terme2"]},
            "Cat3": {"EN": ["term3"], "FR": ["terme3"]},
        }

        result = await bidsandtenders_scrape(portal, keywords)

        # extract_listings_from_html should be called at least 3 times
        # (once per category OR query)
        assert mock_extract.call_count >= 3

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_results_aggregated_across_categories(
        self, mock_pw_func, mock_extract
    ):
        """Verify listings from different categories are combined."""
        portal = _make_portal()

        call_count = {"n": 0}

        def side_effect(html, name):
            call_count["n"] += 1
            batch = call_count["n"]
            return [
                _make_listing(f"L{batch}-{i}", f"ID-{batch}-{i}")
                for i in range(3)
            ]

        mock_extract.side_effect = side_effect

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        keywords = {
            "Cat1": {"EN": ["term1"], "FR": ["terme1"]},
            "Cat2": {"EN": ["term2"], "FR": ["terme2"]},
        }

        result = await bidsandtenders_scrape(portal, keywords)
        assert len(result.listings) == 6  # 3 + 3, all unique IDs

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_results_deduplicated(self, mock_pw_func, mock_extract):
        """Verify duplicate source_listing_ids are removed."""
        portal = _make_portal()

        call_count = {"n": 0}

        def side_effect(html, name):
            call_count["n"] += 1
            return [
                _make_listing(f"Listing-{call_count['n']}", "DUP-1"),
                _make_listing(
                    f"Unique-{call_count['n']}",
                    f"UNIQUE-{call_count['n']}",
                ),
            ]

        mock_extract.side_effect = side_effect

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        keywords = {
            "Cat1": {"EN": ["term1"]},
            "Cat2": {"EN": ["term2"]},
        }

        result = await bidsandtenders_scrape(portal, keywords)
        # 2 categories x 2 listings = 4, minus 1 duplicate "DUP-1" = 3
        assert len(result.listings) == 3


# ---------------------------------------------------------------------------
# TestSearchFallback
# ---------------------------------------------------------------------------


class TestSearchFallback:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_or_zero_results_triggers_individual(
        self, mock_pw_func, mock_extract
    ):
        """When OR query returns 0 results, individual keyword searches run."""
        portal = _make_portal()

        call_count = {"n": 0}

        def side_effect(html, name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return []
            return [
                _make_listing(
                    f"Individual-{call_count['n']}",
                    f"IND-{call_count['n']}",
                )
            ]

        mock_extract.side_effect = side_effect

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        keywords = {
            "Cat1": {"EN": ["term1", "term2"]},
        }

        result = await bidsandtenders_scrape(portal, keywords)
        assert len(result.listings) >= 1
        assert result.search_used is True

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_fallback_persists_across_categories(
        self, mock_pw_func, mock_extract
    ):
        """Once OR fails, subsequent categories skip OR and go straight to individual."""
        portal = _make_portal()

        search_queries = []

        page = _make_mock_page()

        async def capture_fill(text):
            search_queries.append(text)

        page._searchbox_locator.fill = AsyncMock(side_effect=capture_fill)

        _setup_playwright_mock(mock_pw_func, page)

        call_count = {"n": 0}

        def side_effect(html, name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return []
            return [
                _make_listing(f"L-{call_count['n']}", f"ID-{call_count['n']}")
            ]

        mock_extract.side_effect = side_effect

        keywords = {
            "Cat1": {"EN": ["a1"]},
            "Cat2": {"EN": ["b1"]},
        }

        result = await bidsandtenders_scrape(portal, keywords)

        or_queries = [q for q in search_queries if q and " OR " in q]
        # Only 1 OR query should have been attempted (for Cat1)
        assert len(or_queries) <= 1

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_individual_searches_reset_between(
        self, mock_pw_func, mock_extract
    ):
        """Verify _reset_search is called between individual keyword searches."""
        portal = _make_portal()

        call_count = {"n": 0}

        def side_effect(html, name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return []  # OR fails
            return [
                _make_listing(f"L-{call_count['n']}", f"ID-{call_count['n']}")
            ]

        mock_extract.side_effect = side_effect

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        keywords = {
            "Cat1": {"EN": ["term1", "term2", "term3"]},
        }

        result = await bidsandtenders_scrape(portal, keywords)

        # Reset button click should have been called multiple times
        reset_locator = page._reset_locator
        assert reset_locator.click.call_count >= 2


# ---------------------------------------------------------------------------
# TestSearchBoxNotFound
# ---------------------------------------------------------------------------


class TestSearchBoxNotFound:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_no_search_box_falls_back_to_full_scrape(
        self, mock_pw_func, mock_extract
    ):
        """When no search box is found, extract from full page content."""
        portal = _make_portal()
        full_page_listings = [
            _make_listing("Full-1", "FP-1"),
            _make_listing("Full-2", "FP-2"),
        ]
        mock_extract.return_value = full_page_listings

        page = _make_mock_page(
            searchbox_visible=False,
            placeholder_visible=False,
            input_text_visible=False,
        )
        _setup_playwright_mock(mock_pw_func, page)

        keywords = _sample_keywords_by_category()
        result = await bidsandtenders_scrape(portal, keywords)
        assert len(result.listings) == 2
        assert result.listings[0].title == "Full-1"

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_no_search_box_returns_search_used_false(
        self, mock_pw_func, mock_extract
    ):
        """search_used is False when search box not found."""
        portal = _make_portal()
        mock_extract.return_value = [_make_listing()]

        page = _make_mock_page(
            searchbox_visible=False,
            placeholder_visible=False,
            input_text_visible=False,
        )
        _setup_playwright_mock(mock_pw_func, page)

        keywords = _sample_keywords_by_category()
        result = await bidsandtenders_scrape(portal, keywords)
        assert result.search_used is False

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_no_keywords_falls_back_to_full_scrape(
        self, mock_pw_func, mock_extract
    ):
        """When keywords_by_category is None, extract from full page."""
        portal = _make_portal()
        mock_extract.return_value = [_make_listing("Full-1", "FP-1")]

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        result = await bidsandtenders_scrape(portal, keywords_by_category=None)
        assert len(result.listings) == 1
        assert result.search_used is False

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_no_keywords_returns_search_used_false(
        self, mock_pw_func, mock_extract
    ):
        """search_used is False when no keywords provided."""
        portal = _make_portal()
        mock_extract.return_value = []

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        result = await bidsandtenders_scrape(portal)
        assert result.search_used is False


# ---------------------------------------------------------------------------
# TestBidsAndTendersScrapeSignature
# ---------------------------------------------------------------------------


class TestBidsAndTendersScrapeSignature:
    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_keywords_parameter_is_optional(
        self, mock_pw_func, mock_extract
    ):
        """Calling with just portal still works (backward compatible)."""
        portal = _make_portal()
        mock_extract.return_value = []

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        result = await bidsandtenders_scrape(portal)
        assert isinstance(result, BidsAndTendersResult)

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_returns_bidsandtenders_result(
        self, mock_pw_func, mock_extract
    ):
        """Return type is BidsAndTendersResult with listings and search_used."""
        portal = _make_portal()
        mock_extract.return_value = [_make_listing()]

        page = _make_mock_page()
        _setup_playwright_mock(mock_pw_func, page)

        result = await bidsandtenders_scrape(portal)
        assert isinstance(result, BidsAndTendersResult)
        assert hasattr(result, "listings")
        assert hasattr(result, "search_used")

    @pytest.mark.asyncio
    @patch("scraper.pipeline.bidsandtenders.extract_listings_from_html")
    @patch("scraper.pipeline.bidsandtenders.async_playwright")
    async def test_search_used_true_when_search_performed(
        self, mock_pw_func, mock_extract
    ):
        """search_used is True when keywords provided and search box found."""
        portal = _make_portal()
        mock_extract.return_value = [_make_listing("L1", "ID-1")]

        page = _make_mock_page(searchbox_visible=True)
        _setup_playwright_mock(mock_pw_func, page)

        keywords = _sample_keywords_by_category()
        result = await bidsandtenders_scrape(portal, keywords)
        assert result.search_used is True
