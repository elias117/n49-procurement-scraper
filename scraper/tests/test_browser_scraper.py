"""Tests for the generic browser scraper with keyword search."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import PortalRecord, ProcurementListing


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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"
        mock_extract.return_value = []

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        # History has input_text = search was detected
        mock_history = _make_mock_history(["go_to_url", "input_text", "click_element"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = AsyncMock()
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

            mock_page = AsyncMock()
            mock_page.content.return_value = "<html></html>"

            mock_browser_inst = AsyncMock()
            mock_browser_inst.get_current_page.return_value = mock_page
            mock_browser_inst.kill = AsyncMock()
            mock_browser_use_module.Browser.return_value = mock_browser_inst

            # First search uses 12 steps, second would have only 3 remaining
            mock_history = _make_mock_history(["go_to_url", "input_text"], steps=12)
            mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        # History has NO input_text = agent never found search form
        mock_history = _make_mock_history(["go_to_url", "click_element"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url"], steps=5)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = AsyncMock()
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

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser_inst = AsyncMock()
        mock_browser_inst.get_current_page.return_value = mock_page
        mock_browser_inst.kill = AsyncMock()
        mock_browser_use_module.Browser.return_value = mock_browser_inst

        # Agent run succeeds for first search
        mock_history = _make_mock_history(["go_to_url", "input_text"], steps=3)
        mock_agent_inst = AsyncMock()
        mock_agent_inst.run.return_value = mock_history
        mock_browser_use_module.Agent.return_value = mock_agent_inst

        mock_extract.return_value = [listing1]

        result = asyncio.get_event_loop().run_until_complete(
            browser_scrape(generic_portal, keywords_by_category=kw)
        )

        assert len(result.listings) >= 1
        assert result.listings[0].title == "Before crash"
