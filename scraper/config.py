"""
Scraper pipeline configuration.

Loads settings from environment variables. Required variables raise ValueError
at import time if not set.
"""

import os
import logging

# ---------------------------------------------------------------------------
# Required environment variables (fail fast at import)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Example: postgresql://user:pass@host:5432/dbname"
    )

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY environment variable is required."
    )

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
