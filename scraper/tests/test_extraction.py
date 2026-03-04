"""
Tests for LLM extraction pipeline (scraper/pipeline/extraction.py).

All tests mock OpenAI and instructor -- no real API calls are made.
"""

from unittest.mock import MagicMock, patch

import openai
import pytest

from scraper.models import ExtractionResult, ProcurementListing
from scraper.pipeline.extraction import (
    CANADIAN_PROVINCES,
    EXTRACTION_SYSTEM_PROMPT,
    extract_listing_detail,
    extract_listings_from_html,
    strip_html,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_html():
    """HTML page with script, style, nav, and footer tags."""
    return """
    <html>
    <head>
        <script>var x = 1; console.log("tracking");</script>
        <style>.header { color: red; font-size: 14px; }</style>
    </head>
    <body>
        <nav class="main-nav"><a href="/">Home</a><a href="/about">About</a></nav>
        <header id="site-header"><h1>Portal Header</h1></header>
        <aside class="sidebar">Sidebar content here</aside>
        <div class="content">
            <h2>Open Tenders</h2>
            <p>Tender RFP-2026-001: Network Equipment Supply</p>
            <p>Closing Date: March 30, 2026</p>
        </div>
        <footer class="site-footer"><p>Copyright 2026</p></footer>
    </body>
    </html>
    """


@pytest.fixture
def table_html():
    """HTML page with a procurement listing table."""
    return """
    <html>
    <body>
    <table class="listing-table">
        <thead>
            <tr>
                <th>Reference</th><th>Title</th><th>Closing Date</th><th>Status</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>RFP-2026-001</td>
                <td><a href="/listing/001">Network Equipment Supply</a></td>
                <td>March 30, 2026</td>
                <td>Open</td>
            </tr>
            <tr>
                <td>RFP-2026-002</td>
                <td><a href="/listing/002">Building Maintenance Services</a></td>
                <td>April 15, 2026</td>
                <td>Open</td>
            </tr>
        </tbody>
    </table>
    </body>
    </html>
    """


@pytest.fixture
def large_html():
    """~50KB HTML with lots of cruft to verify size reduction."""
    # Build HTML with scripts, styles, nav, and repeated content to hit ~50KB
    scripts = ('<script>var data = "' + "x" * 4000 + '";</script>\n') * 10
    styles = ('<style>.cls-' + "a" * 4000 + ' { color: red; }</style>\n') * 3
    nav = '<nav>' + ('<a href="#" class="nav-item extra-long-class-name">' + "Link " * 10 + '</a>') * 100 + '</nav>'
    footer = '<footer>' + ('<p class="footer-item">' + "Footer " * 10 + '</p>') * 100 + '</footer>'
    content = '<div class="content">'
    for i in range(20):
        content += f'<p>Procurement listing {i}: Supply of office materials</p>\n'
    content += '</div>'

    html = f"<html><head>{scripts}{styles}</head><body>{nav}{content}{footer}</body></html>"
    return html


@pytest.fixture
def mock_extraction_result():
    """A pre-built ExtractionResult with 2 listings."""
    return ExtractionResult(
        listings=[
            ProcurementListing(
                title="Network Equipment Supply",
                reference_number="RFP-2026-001",
                closing_date="2026-03-30",
                status="open",
            ),
            ProcurementListing(
                title="Building Maintenance Services",
                reference_number="RFP-2026-002",
                closing_date="2026-04-15",
                status="open",
            ),
        ]
    )


@pytest.fixture
def mock_single_listing():
    """A single ProcurementListing for detail extraction tests."""
    return ProcurementListing(
        title="Network Equipment Supply",
        reference_number="RFP-2026-001",
        description="Supply and installation of network equipment.",
        closing_date="2026-03-30",
        status="open",
    )


# ---------------------------------------------------------------------------
# strip_html tests
# ---------------------------------------------------------------------------


class TestStripHtml:
    """Tests for the strip_html function."""

    def test_strip_html_removes_scripts(self, simple_html):
        """Script tags and their contents should be removed."""
        result = strip_html(simple_html)
        assert "tracking" not in result
        assert "console.log" not in result
        assert "var x" not in result

    def test_strip_html_removes_nav_footer(self, simple_html):
        """Nav, footer, header, and aside tags should be removed."""
        result = strip_html(simple_html)
        assert "main-nav" not in result
        assert "Home" not in result
        assert "About" not in result
        assert "Copyright 2026" not in result
        assert "Portal Header" not in result
        assert "Sidebar content" not in result

    def test_strip_html_preserves_content(self, table_html):
        """Meaningful content like table text should be preserved."""
        result = strip_html(table_html)
        assert "RFP-2026-001" in result
        assert "Network Equipment Supply" in result
        assert "RFP-2026-002" in result
        assert "Building Maintenance Services" in result
        assert "March 30, 2026" in result
        assert "Open" in result

    def test_strip_html_reduces_size(self, large_html):
        """Large HTML with cruft should be reduced by 5-10x or more."""
        original_size = len(large_html)
        result = strip_html(large_html)
        stripped_size = len(result)

        # The large HTML has ~50KB of scripts/styles/nav/footer
        # After stripping, only the 20 listing paragraphs should remain
        assert original_size > 40000, f"Test HTML should be >40KB, got {original_size}"
        reduction = original_size / stripped_size if stripped_size > 0 else 0
        assert reduction >= 5, (
            f"Expected >=5x reduction, got {reduction:.1f}x "
            f"({original_size} -> {stripped_size})"
        )


class TestCanadianProvincesSet:
    """Sanity checks for the province whitelist used in extraction guidance."""

    def test_contains_all_13_full_names(self):
        expected_full_names = {
            "alberta",
            "british columbia",
            "manitoba",
            "new brunswick",
            "newfoundland and labrador",
            "nova scotia",
            "ontario",
            "prince edward island",
            "quebec",
            "saskatchewan",
            "northwest territories",
            "nunavut",
            "yukon",
        }
        assert expected_full_names.issubset(CANADIAN_PROVINCES)

    def test_contains_common_abbreviations(self):
        expected_abbrev = {
            "ab", "bc", "mb", "nb", "nl", "ns", "on", "pe", "pei",
            "qc", "sk", "nt", "nwt", "nu", "yt",
        }
        assert expected_abbrev.issubset(CANADIAN_PROVINCES)


# ---------------------------------------------------------------------------
# extract_listings_from_html tests
# ---------------------------------------------------------------------------


class TestExtractListingsFromHtml:
    """Tests for the extract_listings_from_html function."""

    @patch("scraper.pipeline.extraction.OpenAI")
    @patch("scraper.pipeline.extraction.instructor")
    def test_extract_listings_calls_instructor(
        self, mock_instructor, mock_openai_cls, table_html
    ):
        """Verify instructor client is called with correct model and response_model."""
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = ExtractionResult(
            listings=[]
        )

        extract_listings_from_html(table_html, "TestPortal")

        # Verify instructor.from_openai was called with an OpenAI instance
        mock_instructor.from_openai.assert_called_once()

        # Verify the chat completion call
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs.kwargs["response_model"] is ExtractionResult
        assert call_kwargs.kwargs["max_retries"] == 2

    @patch("scraper.pipeline.extraction.OpenAI")
    @patch("scraper.pipeline.extraction.instructor")
    def test_extract_listings_system_prompt_contains_never_guess(
        self, mock_instructor, mock_openai_cls, table_html
    ):
        """System prompt must contain NEVER guess instructions."""
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = ExtractionResult(
            listings=[]
        )

        extract_listings_from_html(table_html, "TestPortal")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        system_msg = messages[0]["content"]

        assert "NEVER guess" in system_msg
        assert "NAICS" in system_msg
        assert "UNSPSC" in system_msg
        assert "GSIN" in system_msg
        assert "dollar values" in system_msg
        assert "dates" in system_msg
        assert "Province must be one of the 13 Canadian provinces/territories" in system_msg

    @patch("scraper.pipeline.extraction.OpenAI")
    @patch("scraper.pipeline.extraction.instructor")
    def test_extract_listings_returns_procurement_listings(
        self, mock_instructor, mock_openai_cls, table_html, mock_extraction_result
    ):
        """Mock returns ExtractionResult with 2 listings, verify list returned."""
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_extraction_result

        result = extract_listings_from_html(table_html, "TestPortal")

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(l, ProcurementListing) for l in result)
        assert result[0].title == "Network Equipment Supply"
        assert result[1].title == "Building Maintenance Services"

    def test_extract_listings_empty_html_returns_empty(self):
        """Empty or very short HTML returns empty list without calling LLM."""
        # Completely empty
        assert extract_listings_from_html("", "TestPortal") == []

        # Very short (under 50 chars after stripping)
        assert extract_listings_from_html("<p>Hi</p>", "TestPortal") == []

    @patch("scraper.pipeline.extraction.OpenAI")
    @patch("scraper.pipeline.extraction.instructor")
    def test_extraction_retries_on_rate_limit(
        self, mock_instructor, mock_openai_cls, table_html, mock_extraction_result
    ):
        """Verify retry on RateLimitError: first call fails, second succeeds."""
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client

        # Build a realistic RateLimitError
        rate_limit_error = openai.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )

        # First call raises, second succeeds
        mock_client.chat.completions.create.side_effect = [
            rate_limit_error,
            mock_extraction_result,
        ]

        result = extract_listings_from_html(table_html, "TestPortal")

        assert len(result) == 2
        assert mock_client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# extract_listing_detail tests
# ---------------------------------------------------------------------------


class TestExtractListingDetail:
    """Tests for the extract_listing_detail function."""

    @patch("scraper.pipeline.extraction.OpenAI")
    @patch("scraper.pipeline.extraction.instructor")
    def test_extract_listing_detail_returns_single(
        self, mock_instructor, mock_openai_cls, table_html, mock_single_listing
    ):
        """Verify single ProcurementListing returned from detail page."""
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_single_listing

        result = extract_listing_detail(table_html, "TestPortal")

        assert isinstance(result, ProcurementListing)
        assert result.title == "Network Equipment Supply"
        assert result.reference_number == "RFP-2026-001"

        # Verify response_model is ProcurementListing (not ExtractionResult)
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["response_model"] is ProcurementListing
