"""
Tests for robots.txt compliance helpers.
"""

import unittest
from unittest.mock import patch
from urllib.error import URLError

from scraper.pipeline.robots import is_scraping_allowed_by_robots


class _FakeResponse:
    def __init__(self, text: str):
        self._text = text

    def read(self):
        return self._text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestRobotsCompliance(unittest.TestCase):
    @patch("scraper.pipeline.robots.urlopen")
    def test_allows_scraping_when_robots_permits(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse("User-agent: *\nAllow: /\n")

        allowed = is_scraping_allowed_by_robots("https://example.com/tenders/open")

        assert allowed is True

    @patch("scraper.pipeline.robots.urlopen")
    def test_blocks_scraping_when_robots_disallows_path(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            "User-agent: *\nDisallow: /tenders/private\n"
        )

        with self.assertLogs("scraper.robots", level="WARNING") as logs:
            allowed = is_scraping_allowed_by_robots(
                "https://example.com/tenders/private/rfp-123"
            )

        assert allowed is False
        assert any("Blocked by robots.txt" in message for message in logs.output)

    @patch("scraper.pipeline.robots.urlopen", side_effect=URLError("timeout"))
    def test_fail_open_when_robots_check_errors(self, _mock_urlopen):
        with self.assertLogs("scraper.robots", level="WARNING") as logs:
            allowed = is_scraping_allowed_by_robots("https://example.com/tenders/open")

        assert allowed is True
        assert any(
            "Allowed due to robots.txt check error (fail-open)" in message
            for message in logs.output
        )
