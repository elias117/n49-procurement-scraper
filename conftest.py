"""Root conftest — sets dummy environment variables before any test imports.

This ensures api.config and scraper.config can be imported without crashing
in CI or local dev environments where real credentials are absent.
"""
import os


def pytest_configure(config):
    """Set dummy env vars before collection begins."""
    os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost/dummy")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
