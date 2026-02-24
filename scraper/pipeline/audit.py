"""
Scrape run audit logging wrappers.

Thin layer around db.py scrape run functions that adds structured logging
and timing. Used by the orchestrator to log every pipeline run.
"""

import logging

from scraper import db
from scraper.models import PortalRecord

logger = logging.getLogger("scraper.audit")


def start_run(conn, portal: PortalRecord) -> str:
    """
    Start a new scrape run for a portal.

    Args:
        conn: psycopg2 connection.
        portal: The portal being scraped.

    Returns:
        The UUID of the new scrape run as a string.
    """
    run_id = db.start_scrape_run(conn, portal.id)
    logger.info("Starting scrape run for %s (%s)", portal.name, portal.url)
    return run_id


def complete_run(conn, run_id: str, portal: PortalRecord, stats: dict) -> None:
    """
    Mark a scrape run as completed with stats.

    Args:
        conn: psycopg2 connection.
        run_id: UUID of the scrape run.
        portal: The portal that was scraped.
        stats: Dict with keys: found, new, updated.
    """
    db.complete_scrape_run(conn, run_id, stats)
    logger.info(
        "Completed %s: %d found, %d new, %d updated",
        portal.name,
        stats.get("found", 0),
        stats.get("new", 0),
        stats.get("updated", 0),
    )


def fail_run(conn, run_id: str, portal: PortalRecord, error: Exception) -> None:
    """
    Mark a scrape run as failed and check auto-disable.

    Args:
        conn: psycopg2 connection.
        run_id: UUID of the scrape run.
        portal: The portal that failed.
        error: The exception that caused the failure.
    """
    db.fail_scrape_run(conn, run_id, str(error))
    logger.error("Failed %s: %s", portal.name, error)

    was_disabled = db.check_auto_disable(conn, portal.id)
    if was_disabled:
        logger.warning(
            "Portal %s has been auto-disabled after consecutive failures",
            portal.name,
        )
