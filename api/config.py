"""
API service configuration.

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


def get_openai_api_key() -> str | None:
    """Return OPENAI_API_KEY or None if unset."""
    return os.environ.get("OPENAI_API_KEY")


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
# Static settings (safe to resolve at import time)
# ---------------------------------------------------------------------------
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

# RRF parameter (k=60 is the original paper default; configurable for tuning)
RRF_K = int(os.environ.get("RRF_K", "60"))

# Oversampling: fetch this many candidates from each sub-query before RRF merge
RRF_OVERSAMPLE_FACTOR = int(os.environ.get("RRF_OVERSAMPLE_FACTOR", "4"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api")
