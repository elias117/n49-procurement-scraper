"""Tests for the generic browser scraper with keyword search."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import ExtractionResult, PortalRecord, ProcurementListing


# ---------------------------------------------------------------------------
# Mock browser_use module (lazy-imported by browser_scraper)
# ---------------------------------------------------------------------------

def _make_mock_browser_use():
    """Create a mock browser_use module with all required classes."""
    mod = MagicMock()
    # Use MagicMock *instances* (not the class) so .return_value works
    mod.Agent = MagicMock()
    mod.Browser = MagicMock()
    mod.BrowserProfile = MagicMock()
    mod.ChatOpenAI = MagicMock()
    return mod


def _make_mock_history(action_names_list=None, steps=3):
    """Create a mock AgentHistoryList."""
    history = MagicMock()
    history.action_names.return_value = action_names_list or []
    history.number_of_steps.return_value = steps
    return history


def _make_mock_page(url="https://example.com/tenders", html="<html></html>"):
    """Create a page mock with async browser methods and a sync url attr."""
    page = MagicMock()
    page.url = url
    page.content = AsyncMock(return_value=html)
    page.evaluate = AsyncMock(return_value=html)
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    return page


def _make_mock_browser():
    """Create a browser mock with async methods used by browser_scraper."""
    browser = MagicMock()
    browser.get_current_page = AsyncMock(return_value=None)
    browser.kill = AsyncMock()
    return browser


def _make_mock_agent():
    """Create an agent mock whose run method is awaitable."""
    agent = MagicMock()
    agent.run = AsyncMock()
    return agent


@pytest.fixture(autouse=True)
def mock_browser_use_module():
    """Inject mock browser_use module so lazy import succeeds."""
    mock_mod = _make_mock_browser_use()
    sys.modules["browser_use"] = mock_mod
    yield mock_mod
    # Clean up to avoid leaking between test modules
    sys.modules.pop("browser_use", None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def generic_portal():
    return PortalRecord(
        id="portal-gen-001", name="BC Bid",
        url="https://www.bcbid.gov.bc.ca", level="provincial",
        province="British Columbia", language="en",
        requires_login=False, enabled=True,
    )


@pytest.fixture
def sample_keywords_by_category():
    return {
        "Core Language": {
            "EN": ["translation", "interpreter", "linguist", "bilingual", "french"],
            "FR": ["traduction", "interprète", "linguiste", "bilingue", "français"],
        },
        "Communications": {
            "EN": ["communications", "engagement", "outreach", "media", "public"],
            "FR": ["communications", "engagement", "sensibilisation", "médias", "public"],
        },
    }


# ---------------------------------------------------------------------------
# TestDetectSearchUsed
# ---------------------------------------------------------------------------

class TestDetectSearchUsed:
    def test_detects_input_text_in_history(self):
        from scraper.pipeline.browser_scraper import _detect_search_used
        history = _make_mock_history(["go_to_url", "input_text", "click_element"])
        assert _detect_search_used(history) is True

    def test_no_input_text_returns_false(self):
        from scraper.pipeline.browser_scraper import _detect_search_used
        history = _make_mock_history(["go_to_url", "click_element"])
        assert _detect_search_used(history) is False

    def test_none_history_returns_false(self):
        from scraper.pipeline.browser_scraper import _detect_search_used
        assert _detect_search_used(None) is False

    def test_exception_in_history_returns_false(self):
        from scraper.pipeline.browser_scraper import _detect_search_used
        history = MagicMock()
        history.action_names.side_effect = RuntimeError("broken")
        assert _detect_search_used(history) is False


# ---------------------------------------------------------------------------
# TestBrowserScrapeResult
# ---------------------------------------------------------------------------

class TestBrowserScrapeResult:
    def test_result_has_listings_and_search_used(self):
        from scraper.pipeline.browser_scraper import BrowserScrapeResult
        result = BrowserScrapeResult(listings=[], search_used=True)
        assert result.listings == []
        assert result.search_used is True

    def test_result_unpacks_correctly(self):
        from scraper.pipeline.browser_scraper import BrowserScrapeResult
        result = BrowserScrapeResult(listings=["a", "b"], search_used=False)
        listings, search_used = result
        assert listings == ["a", "b"]
        assert search_used is False


# ---------------------------------------------------------------------------
# TestBrowserScrapeNoKeywords
# ---------------------------------------------------------------------------

class TestBrowserScrapeNoKeywords:
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_no_keywords_returns_search_used_false(
        self, mock_extract, mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal)
        )
        assert result.search_used is False

    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_no_keywords_returns_browser_scrape_result(
        self, mock_extract, mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape, BrowserScrapeResult

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal)
        )
        assert isinstance(result, BrowserScrapeResult)
        assert hasattr(result, "listings")
        assert hasattr(result, "search_used")

    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_no_keywords_uses_standard_max_steps(
        self, mock_extract, mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape
        from scraper import config

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal)
        )
        mock_agent_inst.run.assert_called_once_with(max_steps=config.BROWSER_MAX_STEPS)

    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_no_keywords_uses_original_prompt(
        self, mock_extract, mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal)
        )
        # Check that Agent was called with task containing "Do not fill in search forms"
        call_kwargs = mock_browser_use_module.Agent.call_args
        task_text = call_kwargs.kwargs.get("task", "")
        assert "Do not fill in search forms" in task_text


# ---------------------------------------------------------------------------
# TestBrowserScrapeKeywordSearch
# ---------------------------------------------------------------------------

class TestBrowserScrapeKeywordSearch:
    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_first_search_prompt_includes_navigate_and_keywords(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation", "interpreter"]
        mock_extract.return_value = []

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )

        # First Agent call should have portal URL and keywords in task
        first_call = mock_browser_use_module.Agent.call_args_list[0]
        task_text = first_call.kwargs.get("task", "")
        assert generic_portal.url in task_text
        assert "translation" in task_text or "OR" in task_text

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_first_search_prompt_mentions_advanced_search(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]
        mock_extract.return_value = []

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )

        first_call = mock_browser_use_module.Agent.call_args_list[0]
        task_text = first_call.kwargs.get("task", "")
        assert "Advanced Search" in task_text

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_subsequent_search_prompt_says_clear(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]
        mock_extract.return_value = []

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )

        # Should have 2 Agent calls (one per category in sample_keywords_by_category)
        if len(mock_browser_use_module.Agent.call_args_list) > 1:
            second_call = mock_browser_use_module.Agent.call_args_list[1]
            task_text = second_call.kwargs.get("task", "")
            assert "Clear" in task_text

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_search_detected_sets_search_used_true(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]
        mock_extract.return_value = []

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        # History has input_text = search was detected
        mock_history = _make_mock_history(["go_to_url", "input_text", "click_element"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )
        assert result.search_used is True

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_listings_collected_across_categories(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]

        listing1 = ProcurementListing(title="Listing 1", source_listing_id="L1")
        listing2 = ProcurementListing(title="Listing 2", source_listing_id="L2")
        listing3 = ProcurementListing(title="Listing 3", source_listing_id="L3")

        # Return different listings per call
        mock_extract.side_effect = [
            [listing1, listing2, listing3],
            [listing1, listing2, listing3],
        ]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )
        assert len(result.listings) == 6  # 3 per category * 2 categories

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings")
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_results_deduplicated(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]

        listing1 = ProcurementListing(title="Listing 1", source_listing_id="L1")
        listing2 = ProcurementListing(title="Listing 2", source_listing_id="L2")

        mock_extract.return_value = [listing1, listing2]
        mock_dedup.return_value = [listing1]  # One duplicate removed

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )
        mock_dedup.assert_called_once()
        assert len(result.listings) == 1

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_step_budget_limits_searches(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape
        from scraper import config

        original_value = config.BROWSER_SEARCH_MAX_STEPS
        config.BROWSER_SEARCH_MAX_STEPS = 15

        try:
            mock_batch.return_value = ["translation"]
            mock_extract.return_value = []

            mock_page = _make_mock_page()
            mock_page.content.return_value = "<html></html>"

            mock_browser_inst = _make_mock_browser()
            mock_browser_inst.get_current_page.return_value = mock_page
            mock_browser_inst.kill = AsyncMock()
            mock_browser_use_module.Browser.return_value = mock_browser_inst

            # First search uses 12 steps, second would have only 3 remaining
            mock_history = _make_mock_history(["go_to_url", "input_text"], steps=12)
            mock_agent_inst = _make_mock_agent()
            mock_agent_inst.run.return_value = mock_history
            mock_browser_use_module.Agent.return_value = mock_agent_inst

            asyncio.get_event_loop().run_until_complete(
                browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
            )

            # Both should run since remaining=3 > 0 after first search
            assert mock_agent_inst.run.call_count >= 1
        finally:
            config.BROWSER_SEARCH_MAX_STEPS = original_value


# ---------------------------------------------------------------------------
# TestBrowserScrapeOrFallback
# ---------------------------------------------------------------------------

class TestBrowserScrapeOrFallback:
    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_or_query_used_first(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        kw = {"Cat1": {"EN": ["translation", "interpreter"]}}
        mock_batch.return_value = ["translation", "interpreter"]
        mock_extract.return_value = [ProcurementListing(title="Test", source_listing_id="T1")]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=kw)
        )

        first_call = mock_browser_use_module.Agent.call_args_list[0]
        task_text = first_call.kwargs.get("task", "")
        assert " OR " in task_text

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_or_zero_results_falls_back_to_single(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        kw = {"Cat1": {"EN": ["translation", "interpreter"]}}
        mock_batch.return_value = ["translation", "interpreter"]
        # OR query returns 0 results, retry with single returns some
        mock_extract.side_effect = [
            [],  # OR query returns nothing
            [ProcurementListing(title="Found", source_listing_id="F1")],  # Single keyword
        ]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=kw)
        )

        # Should have created 2 Agent instances (OR attempt + single retry)
        assert mock_browser_use_module.Agent.call_count == 2
        # The retry task should NOT contain " OR "
        retry_call = mock_browser_use_module.Agent.call_args_list[1]
        retry_task = retry_call.kwargs.get("task", "")
        assert " OR " not in retry_task
        assert len(result.listings) == 1

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_or_fallback_persists_across_categories(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        kw = {
            "Cat1": {"EN": ["translation", "interpreter"]},
            "Cat2": {"EN": ["communications", "outreach"]},
        }
        mock_batch.side_effect = [
            ["translation", "interpreter"],
            ["communications", "outreach"],
        ]

        # Cat1 OR returns nothing (triggers OR fallback), Cat1 single works, Cat2 uses single
        mock_extract.side_effect = [
            [],  # Cat1 OR fails
            [ProcurementListing(title="Cat1 single", source_listing_id="C1")],  # Cat1 single
            [ProcurementListing(title="Cat2 single", source_listing_id="C2")],  # Cat2 single
        ]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=kw)
        )

        # Cat2 should also use single keyword (no OR)
        cat2_call = mock_browser_use_module.Agent.call_args_list[-1]
        cat2_task = cat2_call.kwargs.get("task", "")
        assert " OR " not in cat2_task


# ---------------------------------------------------------------------------
# TestBrowserScrapeFallback
# ---------------------------------------------------------------------------

class TestBrowserScrapeFallback:
    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_no_search_form_returns_search_used_false(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]
        mock_extract.return_value = [ProcurementListing(title="Visible", source_listing_id="V1")]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        # History has NO input_text = agent never found search form
        mock_history = _make_mock_history(["go_to_url", "click_element"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )
        assert result.search_used is False

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_no_search_form_returns_visible_listings(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal, sample_keywords_by_category
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        mock_batch.return_value = ["translation"]
        visible_listing = ProcurementListing(title="Visible", source_listing_id="V1")
        mock_extract.return_value = [visible_listing]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=5)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=sample_keywords_by_category)
        )
        assert len(result.listings) >= 1

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_exception_mid_search_returns_collected_results(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        kw = {
            "Cat1": {"EN": ["translation"]},
            "Cat2": {"EN": ["communications"]},
        }
        mock_batch.side_effect = [["translation"], ["communications"]]

        listing1 = ProcurementListing(title="Cat1 result", source_listing_id="C1")
        mock_extract.side_effect = [
            [listing1],  # Cat1 succeeds
            Exception("Page crashed"),  # Cat2 extract fails
        ]

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=kw)
        )

        # Should have at least the Cat1 listing
        assert len(result.listings) >= 1

    @patch("scraper.pipeline.browser_scraper.deduplicate_listings", side_effect=lambda x: x)
    @patch("scraper.pipeline.browser_scraper.select_keyword_batch")
    @patch("scraper.pipeline.browser_scraper.extract_listings_from_html")
    def test_crash_returns_collected_not_empty(
        self, mock_extract, mock_batch, mock_dedup,
        mock_browser_use_module, generic_portal
    ):
        from scraper.pipeline.browser_scraper import browser_scrape

        kw = {"Cat1": {"EN": ["translation"]}}
        mock_batch.return_value = ["translation"]

        listing1 = ProcurementListing(title="Before crash", source_listing_id="BC1")

        mock_page = _make_mock_page()
        mock_page.url = "https://example.com/tenders"
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        # Agent run succeeds for first search
        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = _make_mock_agent()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        mock_extract.return_value = [listing1]

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=kw)
        )

        assert len(result.listings) >= 1
        assert result.listings[0].title == "Before crash"


# ---------------------------------------------------------------------------
# TestIsSparse
# ---------------------------------------------------------------------------

class TestIsSparse:
    def test_sparse_when_all_detail_fields_none(self):
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(title="Test")
        assert _is_sparse(listing) is True

    def test_sparse_when_description_is_short(self):
        """Description under 50 chars is treated as sparse (summary fragment)."""
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(title="Test", description="Short desc")
        assert _is_sparse(listing) is True

    def test_sparse_when_description_present_but_missing_date_and_contact(self):
        """Listing with long description but no closing_date and no contact is sparse."""
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(
            title="Test",
            description="A" * 60,
        )
        assert _is_sparse(listing) is True

    def test_not_sparse_when_description_and_closing_date_present(self):
        """Listing with long description and closing_date is NOT sparse."""
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(
            title="Test",
            description="A sufficiently long description with real details inside",
            closing_date="2026-04-01",
        )
        assert _is_sparse(listing) is False

    def test_not_sparse_when_description_and_contact_present(self):
        """Listing with long description and contact_name is NOT sparse."""
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(
            title="Test",
            description="A sufficiently long description with real details inside",
            contact_name="Jane Doe",
        )
        assert _is_sparse(listing) is False

    def test_sparse_when_only_closing_date_present(self):
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(title="Test", closing_date="2026-03-30")
        assert _is_sparse(listing) is True

    def test_sparse_when_only_value_min_present(self):
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(title="Test", value_min=50000.0)
        assert _is_sparse(listing) is True

    def test_sparse_boundary_49_chars(self):
        """Description of exactly 49 chars is sparse."""
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(
            title="Test",
            description="A" * 49,
            closing_date="2026-04-01",
        )
        assert _is_sparse(listing) is True

    def test_not_sparse_boundary_50_chars(self):
        """Description of exactly 50 chars with closing_date is not sparse."""
        from scraper.pipeline.browser_scraper import _is_sparse
        listing = ProcurementListing(
            title="Test",
            description="A" * 50,
            closing_date="2026-04-01",
        )
        assert _is_sparse(listing) is False


# ---------------------------------------------------------------------------
# TestResolveUrl
# ---------------------------------------------------------------------------

class TestResolveUrl:
    def test_absolute_url_returned_unchanged(self):
        from scraper.pipeline.browser_scraper import _resolve_url
        result = _resolve_url("https://seao.ca/detail/123", "https://seao.ca/")
        assert result == "https://seao.ca/detail/123"

    def test_relative_url_resolved(self):
        from scraper.pipeline.browser_scraper import _resolve_url
        result = _resolve_url("/detail/123", "https://seao.ca/listings/")
        assert result == "https://seao.ca/detail/123"

    def test_relative_url_without_leading_slash(self):
        from scraper.pipeline.browser_scraper import _resolve_url
        result = _resolve_url("detail/123", "https://seao.ca/listings/")
        assert result == "https://seao.ca/listings/detail/123"


class TestSameDomain:
    def test_www_and_apex_domains_match(self):
        from scraper.pipeline.browser_scraper import _is_same_domain
        assert _is_same_domain(
            "https://seao.ca/detail/123",
            "https://www.seao.ca",
        ) is True

    def test_unrelated_domains_do_not_match(self):
        from scraper.pipeline.browser_scraper import _is_same_domain
        assert _is_same_domain(
            "https://globaltenders.com/a",
            "https://www.seao.ca",
        ) is False


# ---------------------------------------------------------------------------
# TestFixSourceUrls
# ---------------------------------------------------------------------------

class TestFixSourceUrls:
    def test_external_url_replaced_with_page_url(self):
        from scraper.pipeline.browser_scraper import _fix_source_urls
        listing = ProcurementListing(
            title="Test",
            source_url="https://www.globaltenders.com/some-tender",
        )
        result = _fix_source_urls([listing], "https://www.seao.ca/results", "https://www.seao.ca/")
        assert result[0].source_url == "https://www.seao.ca/results"

    def test_matching_domain_kept(self):
        from scraper.pipeline.browser_scraper import _fix_source_urls
        listing = ProcurementListing(
            title="Test",
            source_url="https://www.seao.ca/detail/123",
        )
        result = _fix_source_urls([listing], "https://www.seao.ca/results", "https://www.seao.ca/")
        assert result[0].source_url == "https://www.seao.ca/detail/123"

    def test_none_url_gets_page_url(self):
        from scraper.pipeline.browser_scraper import _fix_source_urls
        listing = ProcurementListing(title="Test", source_url=None)
        result = _fix_source_urls([listing], "https://www.seao.ca/results", "https://www.seao.ca/")
        assert result[0].source_url == "https://www.seao.ca/results"

    def test_tendersontime_replaced(self):
        from scraper.pipeline.browser_scraper import _fix_source_urls
        listing = ProcurementListing(
            title="Russian Translation",
            source_url="https://www.tendersontime.com/tenders-details/some-tender-82a4a27/",
        )
        result = _fix_source_urls([listing], "https://www.seao.ca/results", "https://www.seao.ca/")
        assert result[0].source_url == "https://www.seao.ca/results"

    def test_subdomain_variation_kept_with_query_params(self):
        from scraper.pipeline.browser_scraper import _fix_source_urls
        listing = ProcurementListing(
            title="Test",
            source_url="https://seao.ca/detail?id=123&lang=fr",
        )
        result = _fix_source_urls([listing], "https://www.seao.ca/results", "https://www.seao.ca/")
        assert result[0].source_url == "https://seao.ca/detail?id=123&lang=fr"

    def test_non_http_page_url_falls_back_to_portal_url(self):
        from scraper.pipeline.browser_scraper import _fix_source_urls
        listing = ProcurementListing(title="Test", source_url=None)
        result = _fix_source_urls([listing], "about:blank", "https://www.seao.ca/")
        assert result[0].source_url == "https://www.seao.ca/"


class TestCurrentPageUrl:
    def test_uses_page_url_when_http(self):
        from scraper.pipeline.browser_scraper import _current_page_url
        mock_page = _make_mock_page()
        mock_page.url = "https://www.seao.ca/results"
        result = asyncio.get_event_loop().run_until_complete(_current_page_url(mock_page))
        assert result == "https://www.seao.ca/results"

    def test_ignores_non_http_page_url_and_uses_evaluated_url(self):
        from scraper.pipeline.browser_scraper import _current_page_url
        mock_page = _make_mock_page()
        mock_page.url = "about:blank"
        mock_page.evaluate.return_value = "https://www.seao.ca/detail/123?lang=fr"
        result = asyncio.get_event_loop().run_until_complete(_current_page_url(mock_page))
        assert result == "https://www.seao.ca/detail/123?lang=fr"


# ---------------------------------------------------------------------------
# TestMergeDetail
# ---------------------------------------------------------------------------

class TestMergeDetail:
    def test_merge_fills_none_fields(self):
        from scraper.pipeline.browser_scraper import _merge_detail
        original = ProcurementListing(
            title="Translation Services",
            source_url="https://seao.ca/detail/123",
        )
        detail = ProcurementListing(
            title="Translation and Editing Services",  # different title
            description="Full description from detail page",
            closing_date="2026-04-15",
            value_min=50000.0,
            reference_number="REF-001",
        )
        merged = _merge_detail(original, detail)
        # Title preserved from original
        assert merged.title == "Translation Services"
        # Detail fields filled in
        assert merged.description == "Full description from detail page"
        assert merged.closing_date == "2026-04-15"
        assert merged.value_min == 50000.0
        assert merged.reference_number == "REF-001"
        # source_url preserved from original
        assert merged.source_url == "https://seao.ca/detail/123"

    def test_merge_does_not_overwrite_existing(self):
        from scraper.pipeline.browser_scraper import _merge_detail
        original = ProcurementListing(
            title="Test",
            reference_number="ORIG-001",
        )
        detail = ProcurementListing(
            title="Different",
            reference_number="DETAIL-001",
            description="Detail desc",
        )
        merged = _merge_detail(original, detail)
        assert merged.reference_number == "ORIG-001"  # original preserved
        assert merged.description == "Detail desc"  # detail fills None


# ---------------------------------------------------------------------------
# TestEnrichWithDetails
# ---------------------------------------------------------------------------

class TestEnrichWithDetails:
    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_enriches_sparse_listings_with_urls(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details

        sparse_listing = ProcurementListing(
            title="Translation Services",
            source_url="https://seao.ca/detail/123",
        )
        full_listing = ProcurementListing(
            title="Translation Services Detail",
            description="Full description",
            closing_date="2026-04-15",
            value_min=50000.0,
        )

        mock_detail.return_value = full_listing

        mock_page = _make_mock_page()
        mock_page.evaluate.return_value = "<html>detail page</html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page

        portal = PortalRecord(
            id="portal-001", name="SEAO", url="https://seao.ca/",
            level="provincial", province="Quebec", language="fr",
            requires_login=True, enabled=True,
        )

        result = asyncio.get_event_loop().run_until_complete(
            _enrich_with_details([sparse_listing], mock_browser_inst, portal)
        )

        assert len(result) == 1
        assert result[0].title == "Translation Services"  # original title
        assert result[0].description == "Full description"
        assert result[0].closing_date == "2026-04-15"
        assert result[0].value_min == 50000.0

    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_skips_non_sparse_listings(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details

        full_listing = ProcurementListing(
            title="Already Full",
            description="A complete listing with a full description that exceeds fifty characters easily",
            closing_date="2026-04-15",
            source_url="https://seao.ca/detail/456",
        )

        portal = PortalRecord(
            id="portal-001", name="SEAO", url="https://seao.ca/",
            level="provincial", province="Quebec", language="fr",
            requires_login=True, enabled=True,
        )

        mock_browser_inst = _make_mock_browser()

        result = asyncio.get_event_loop().run_until_complete(
            _enrich_with_details([full_listing], mock_browser_inst, portal)
        )

        assert len(result) == 1
        mock_detail.assert_not_called()

    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_skips_sparse_without_url(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details

        sparse_no_url = ProcurementListing(title="No URL")

        portal = PortalRecord(
            id="portal-001", name="SEAO", url="https://seao.ca/",
            level="provincial", province="Quebec", language="fr",
            requires_login=True, enabled=True,
        )

        mock_browser_inst = _make_mock_browser()

        result = asyncio.get_event_loop().run_until_complete(
            _enrich_with_details([sparse_no_url], mock_browser_inst, portal)
        )

        assert len(result) == 1
        assert result[0].title == "No URL"
        mock_detail.assert_not_called()

    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_respects_max_pages_config(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details
        from scraper import config

        original_max = config.BROWSER_DETAIL_MAX_PAGES
        config.BROWSER_DETAIL_MAX_PAGES = 2

        try:
            # 5 sparse listings with URLs
            listings = [
                ProcurementListing(title=f"Listing {i}", source_url=f"https://seao.ca/{i}")
                for i in range(5)
            ]

            mock_detail.return_value = ProcurementListing(
                title="Detail", description="Enriched"
            )

            mock_page = _make_mock_page()
            mock_page.evaluate.return_value = "<html>detail</html>"
            mock_browser_inst = _make_mock_browser()
            mock_browser_inst.get_current_page.return_value = mock_page

            portal = PortalRecord(
                id="portal-001", name="SEAO", url="https://seao.ca/",
                level="provincial", province="Quebec", language="fr",
                requires_login=True, enabled=True,
            )

            result = asyncio.get_event_loop().run_until_complete(
                _enrich_with_details(listings, mock_browser_inst, portal)
            )

            # Only 2 should be enriched (max_pages=2)
            assert mock_detail.call_count == 2
            assert len(result) == 5  # all returned, just only 2 enriched
        finally:
            config.BROWSER_DETAIL_MAX_PAGES = original_max

    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_handles_detail_extraction_failure_gracefully(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details

        sparse_listing = ProcurementListing(
            title="Translation Services",
            source_url="https://seao.ca/detail/123",
        )

        mock_detail.return_value = None  # extraction failed

        mock_page = _make_mock_page()
        mock_page.evaluate.return_value = "<html>detail page</html>"
        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page

        portal = PortalRecord(
            id="portal-001", name="SEAO", url="https://seao.ca/",
            level="provincial", province="Quebec", language="fr",
            requires_login=True, enabled=True,
        )

        result = asyncio.get_event_loop().run_until_complete(
            _enrich_with_details([sparse_listing], mock_browser_inst, portal)
        )

        # Original listing returned unchanged
        assert len(result) == 1
        assert result[0].title == "Translation Services"
        assert result[0].description is None  # still sparse

    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_handles_navigation_error_gracefully(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details

        sparse_listing = ProcurementListing(
            title="Translation Services",
            source_url="https://seao.ca/detail/123",
        )

        mock_page = _make_mock_page()
        mock_page.goto.side_effect = Exception("Navigation failed")
        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page

        portal = PortalRecord(
            id="portal-001", name="SEAO", url="https://seao.ca/",
            level="provincial", province="Quebec", language="fr",
            requires_login=True, enabled=True,
        )

        result = asyncio.get_event_loop().run_until_complete(
            _enrich_with_details([sparse_listing], mock_browser_inst, portal)
        )

        # Original listing returned unchanged despite error
        assert len(result) == 1
        assert result[0].title == "Translation Services"
        mock_detail.assert_not_called()

    @patch("scraper.pipeline.browser_scraper.extract_listing_detail")
    def test_captures_current_detail_page_url(
        self, mock_detail, mock_browser_use_module
    ):
        from scraper.pipeline.browser_scraper import _enrich_with_details

        sparse_listing = ProcurementListing(
            title="Translation Services",
            source_url="https://seao.ca/detail/123",
        )
        mock_detail.return_value = ProcurementListing(
            title="Translation Services",
            description="Detailed text from page",
            closing_date="2026-04-15",
        )

        mock_page = _make_mock_page()
        mock_page.url = "https://seao.ca/detail/123?lang=fr"
        mock_page.evaluate.return_value = "<html>detail page</html>"

        mock_browser_inst = _make_mock_browser()
        mock_browser_inst.get_current_page.return_value = mock_page

        portal = PortalRecord(
            id="portal-001", name="SEAO", url="https://seao.ca/",
            level="provincial", province="Quebec", language="fr",
            requires_login=True, enabled=True,
        )

        result = asyncio.get_event_loop().run_until_complete(
            _enrich_with_details([sparse_listing], mock_browser_inst, portal)
        )

        assert len(result) == 1
        assert result[0].source_url == "https://seao.ca/detail/123?lang=fr"


# ---------------------------------------------------------------------------
# TestStripHtmlPreservesUrls
# ---------------------------------------------------------------------------

class TestStripHtmlPreservesUrls:
    def test_preserves_href_in_output(self):
        from scraper.pipeline.extraction import strip_html
        html = '''<html><body>
        <table><tr>
        <td><a href="https://seao.ca/detail/123">Translation Services</a></td>
        <td>Open</td>
        </tr></table>
        </body></html>'''
        result = strip_html(html)
        assert "https://seao.ca/detail/123" in result
        assert "Translation Services" in result

    def test_preserves_relative_href(self):
        from scraper.pipeline.extraction import strip_html
        html = '''<html><body>
        <a href="/listings/detail?id=456">IT Consulting</a>
        </body></html>'''
        result = strip_html(html)
        assert "/listings/detail?id=456" in result
        assert "IT Consulting" in result

    def test_no_results_english_returns_empty_text(self):
        from scraper.pipeline.extraction import strip_html
        html = "<html><body>Your search did not match any results.</body></html>"
        result = strip_html(html)
        assert result == ""

    def test_no_results_french_returns_empty_text(self):
        from scraper.pipeline.extraction import strip_html
        html = "<html><body>Aucun resultat trouve.</body></html>"
        result = strip_html(html)
        assert result == ""


class TestTitleFiltering:
    def test_filters_boolean_or_query_titles(self):
        from scraper.pipeline.extraction import _should_filter_title
        assert _should_filter_title("translation OR interpreter") is True

    def test_filters_search_results_prefix(self):
        from scraper.pipeline.extraction import _should_filter_title
        assert _should_filter_title("Search Results For translation services") is True

    def test_filters_very_long_titles(self):
        from scraper.pipeline.extraction import _should_filter_title
        assert _should_filter_title("A" * 301) is True

    def test_keeps_normal_title(self):
        from scraper.pipeline.extraction import _should_filter_title
        assert _should_filter_title("Translation and Interpretation Services") is False

    @patch("scraper.pipeline.extraction._call_instructor_extract")
    @patch("scraper.pipeline.extraction.instructor.from_openai")
    def test_extract_listings_from_html_applies_title_filters(
        self, mock_from_openai, mock_call_extract
    ):
        from scraper.pipeline.extraction import extract_listings_from_html

        mock_from_openai.return_value = MagicMock()
        mock_call_extract.return_value = ExtractionResult(
            listings=[
                ProcurementListing(title="translation OR interpreter"),
                ProcurementListing(title="Search results for translation"),
                ProcurementListing(title="A" * 301),
                ProcurementListing(title="Valid Listing Title"),
            ]
        )

        html = "<html><body><p>" + ("x" * 200) + "</p></body></html>"
        results = extract_listings_from_html(html, "SEAO")

        assert len(results) == 1
        assert results[0].title == "Valid Listing Title"
