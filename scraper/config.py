"""
Scraper pipeline configuration.

Loads settings from environment variables. Required variables are validated
lazily via helper functions so that importing this module never fails — tests
can import any module without needing real credentials.
"""

import os
import logging


# ---------------------------------------------------------------------------
# Required environment variables (lazy — validated on first use)
# ---------------------------------------------------------------------------
def get_database_url() -> str:
    """Return DATABASE_URL or raise if unset."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Example: postgresql://user:pass@host:5432/dbname"
        )
    return url


def get_openai_api_key() -> str:
    """Return OPENAI_API_KEY or raise if unset."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY environment variable is required.")
    return key


# Backward-compat: modules that read config.DATABASE_URL / config.OPENAI_API_KEY
# at call time (not import time) still work via these module-level names.
# They resolve to the current env value on every access through __getattr__.
_LAZY_VARS = {
    "DATABASE_URL": get_database_url,
    "OPENAI_API_KEY": get_openai_api_key,
}


def __getattr__(name: str):
    if name in _LAZY_VARS:
        return _LAZY_VARS[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# OpenAI model settings
# ---------------------------------------------------------------------------
OPENAI_EXTRACTION_MODEL: str = os.environ.get(
    "OPENAI_EXTRACTION_MODEL", "gpt-4o-mini"
)

# Locked: changing embedding model requires full re-indexing of all listings
OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

EMBEDDING_DIMENSIONS: int = 1536
MAX_EMBEDDING_TOKENS: int = 8000  # leave margin below 8192 limit
EMBEDDING_BATCH_TOKEN_LIMIT: int = 250_000
EMBEDDING_BATCH_SIZE_LIMIT: int = 2048

# ---------------------------------------------------------------------------
# Browser automation settings
# ---------------------------------------------------------------------------
# POC confirmed: headless=True gets 403-blocked by procurement portals.
# Must use headless=False with Xvfb in Docker.
BROWSER_HEADLESS: bool = False
BROWSER_WAIT_NETWORK_IDLE: float = float(
    os.environ.get("BROWSER_WAIT_NETWORK_IDLE", "2.0")
)
BROWSER_WAIT_BETWEEN_ACTIONS: float = float(
    os.environ.get("BROWSER_WAIT_BETWEEN_ACTIONS", "1.0")
)
BROWSER_MAX_STEPS: int = int(os.environ.get("BROWSER_MAX_STEPS", "10"))
BROWSER_SEARCH_MAX_STEPS: int = int(
    os.environ.get("BROWSER_SEARCH_MAX_STEPS", "50")
)
BROWSER_DETAIL_MAX_PAGES: int = int(
    os.environ.get("BROWSER_DETAIL_MAX_PAGES", "10")
)

# ---------------------------------------------------------------------------
# Portal management
# ---------------------------------------------------------------------------
PORTAL_CONSECUTIVE_FAILURE_THRESHOLD: int = int(
    os.environ.get("PORTAL_CONSECUTIVE_FAILURE_THRESHOLD", "5")
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("scraper")
