"""Unit tests for keyword highlight sanitization."""
from api.search.highlights import sanitize_snippet


def test_sanitize_preserves_mark_tags():
    """<mark> tags from ts_headline should be preserved."""
    input_html = "procurement of <mark>IT services</mark> for federal"
    result = sanitize_snippet(input_html)
    assert result == "procurement of <mark>IT services</mark> for federal"


def test_sanitize_strips_script_tags():
    """Script tags must be stripped to prevent XSS.

    bleach strips the <script> tags but preserves the text content,
    which is safe since the JS cannot execute without the tags.
    """
    input_html = "some text <script>alert('xss')</script> more text"
    result = sanitize_snippet(input_html)
    assert "<script>" not in result
    assert "</script>" not in result
    assert "some text" in result
    assert "more text" in result


def test_sanitize_strips_html_preserving_text():
    """Non-mark HTML tags should be stripped but their text content preserved."""
    input_html = "<b>bold</b> and <mark>highlight</mark>"
    result = sanitize_snippet(input_html)
    assert result == "bold and <mark>highlight</mark>"


def test_sanitize_handles_nested_tags():
    """Nested tags should be stripped, keeping only <mark>."""
    input_html = "<div><mark>word</mark></div>"
    result = sanitize_snippet(input_html)
    assert result == "<mark>word</mark>"


def test_sanitize_empty_string():
    """Empty input should return empty string."""
    assert sanitize_snippet("") == ""
