"""
robots.txt compliance helpers for portal scraping.

Policy:
- If robots.txt explicitly disallows the portal URL path for our user agent,
  block scraping for that portal.
- If robots.txt cannot be fetched or parsed, fail open (allow) and log.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

logger = logging.getLogger("scraper.robots")

# Conservative bot-style agent string for robots.txt checks.
ROBOTS_USER_AGENT = "n49-procurement-scraper-bot"
ROBOTS_FETCH_TIMEOUT_SECONDS = 10.0


def _robots_txt_url(portal_url: str) -> str:
    """Build robots.txt URL from a portal URL."""
    parts = urlsplit(portal_url)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"Invalid portal URL: {portal_url}")
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


def is_scraping_allowed_by_robots(
    portal_url: str,
    user_agent: str = ROBOTS_USER_AGENT,
    timeout_seconds: float = ROBOTS_FETCH_TIMEOUT_SECONDS,
) -> bool:
    """
    Return True when scraping the portal URL is allowed by robots.txt.

    Fail-open behavior:
    Any fetch or parse error allows scraping and is logged for auditability.
    """
    robots_url = _robots_txt_url(portal_url)

    try:
        request = Request(robots_url, headers={"User-Agent": user_agent})
        with urlopen(request, timeout=timeout_seconds) as response:
            robots_text = response.read().decode("utf-8", errors="replace")

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(robots_text.splitlines())

        allowed = parser.can_fetch(user_agent, portal_url)
        if not allowed:
            logger.warning(
                "Blocked by robots.txt: portal_url=%s robots_url=%s user_agent=%s",
                portal_url,
                robots_url,
                user_agent,
            )
        return allowed
    except Exception as exc:
        logger.warning(
            "Allowed due to robots.txt check error (fail-open): "
            "portal_url=%s robots_url=%s user_agent=%s error=%s",
            portal_url,
            robots_url,
            user_agent,
            exc,
        )
        return True
