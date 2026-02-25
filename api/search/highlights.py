"""Keyword highlight sanitization for ts_headline output.

PostgreSQL's ts_headline output is NOT safe for direct rendering --
it can contain arbitrary HTML from source documents. This module strips
all HTML except our <mark> highlight tags to prevent XSS.
"""
from __future__ import annotations

import bleach

# ts_headline configuration string for SQL queries.
# MaxFragments=2 returns up to 2 highlighted fragments.
# FragmentDelimiter joins them with ellipsis.
TS_HEADLINE_OPTIONS = (
    "MaxWords=35, MinWords=15, "
    "StartSel=<mark>, StopSel=</mark>, "
    "MaxFragments=2, FragmentDelimiter= ... "
)


def sanitize_snippet(raw_snippet: str) -> str:
    """Strip all HTML tags from ts_headline output except <mark>.

    Args:
        raw_snippet: Raw ts_headline output that may contain arbitrary HTML
            from the source document text.

    Returns:
        Sanitized string with only <mark>...</mark> tags preserved.
    """
    if not raw_snippet:
        return ""

    return bleach.clean(raw_snippet, tags=["mark"], strip=True)
