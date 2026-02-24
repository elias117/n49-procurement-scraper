"""
Pipeline orchestrator.

Ties all pipeline modules together: portal dispatch, scrape -> validate ->
embed -> upsert flow, per-portal error isolation, and sequential processing.

CRITICAL: Per-portal error isolation -- a failed portal MUST NOT stop the
pipeline. Each portal is wrapped in try/except.

Sequential processing (not parallel) due to 4GB container memory constraint.
"""

import logging
from typing import Optional

from scraper.db import (
    db_connection,
    get_enabled_portals,
    get_portal_by_name,
    upsert_listings,
)
from scraper.models import PortalRecord, ProcurementListing, to_listing_record
from scraper.pipeline.audit import start_run, complete_run, fail_run
from scraper.pipeline.canadabuys import canadabuys_ingest
from scraper.pipeline.bidsandtenders import bidsandtenders_scrape
from scraper.pipeline.browser_scraper import browser_scrape
from scraper.pipeline.validation import validate_and_score
from scraper.pipeline.embeddings import generate_embeddings

logger = logging.getLogger("scraper.orchestrator")


def classify_portal(portal: PortalRecord) -> str:
    """
    Classify a portal to determine which scraper handler to use.

    Args:
        portal: The portal to classify.

    Returns:
        One of: "canadabuys", "bidsandtenders", "browser".
    """
    if portal.name == "CanadaBuys":
        return "canadabuys"
    if "bidsandtenders" in portal.url:
        return "bidsandtenders"
    return "browser"


async def scrape_portal(portal: PortalRecord) -> list:
    """
    Dispatch a portal to the correct scraper handler.

    Args:
        portal: The portal to scrape.

    Returns:
        List of ProcurementListing (canadabuys returns ListingRecord directly).
    """
    portal_type = classify_portal(portal)

    if portal_type == "canadabuys":
        return await canadabuys_ingest(portal)
    elif portal_type == "bidsandtenders":
        return await bidsandtenders_scrape(portal)
    else:
        return await browser_scrape(portal)


async def process_portal(conn, portal: PortalRecord) -> dict:
    """
    Full pipeline for ONE portal: scrape -> validate -> embed -> upsert -> audit.

    Per-portal error isolation: catches ALL exceptions so a failed portal
    does not stop the pipeline.

    Args:
        conn: psycopg2 connection.
        portal: The portal to process.

    Returns:
        Dict with keys: found, new, updated (and optionally "error").
    """
    run_id = start_run(conn, portal)

    try:
        # Step 1: Scrape
        raw_listings = await scrape_portal(portal)
        logger.info(
            "Portal %s: %d raw listings scraped", portal.name, len(raw_listings)
        )

        # Step 2: Convert ProcurementListing -> ListingRecord
        # canadabuys_ingest already returns ListingRecord, but browser scrapers
        # return ProcurementListing. Check and convert as needed.
        listing_records = []
        for item in raw_listings:
            if isinstance(item, ProcurementListing):
                listing_records.append(
                    to_listing_record(item, portal.id, portal.language)
                )
            else:
                # Already a ListingRecord (e.g., from canadabuys)
                listing_records.append(item)

        # Step 3: Validate and score (filter out ValueError for missing title)
        validated = []
        for record in listing_records:
            try:
                validated.append(validate_and_score(record))
            except ValueError as ve:
                logger.warning(
                    "Skipping listing (validation failed): %s", ve
                )

        logger.info(
            "Portal %s: %d validated out of %d records",
            portal.name,
            len(validated),
            len(listing_records),
        )

        # Step 4: Generate embeddings (only on validated listings)
        embedded = generate_embeddings(validated)

        # Step 5: Upsert to database
        stats = upsert_listings(conn, portal.id, embedded)

        # Step 6: Audit completion
        complete_run(conn, run_id, portal, stats)

        return stats

    except Exception as e:
        fail_run(conn, run_id, portal, e)
        logger.exception("Portal %s failed", portal.name)
        return {"found": 0, "new": 0, "updated": 0, "error": str(e)}


async def run_pipeline(portal_name: Optional[str] = None) -> dict:
    """
    Run the scraper pipeline for all enabled portals (or a single portal).

    Processes portals SEQUENTIALLY (not parallel) due to 4GB container
    memory constraint.

    Args:
        portal_name: If provided, run only this portal. Otherwise run all enabled.

    Returns:
        Dict mapping portal_name -> stats dict.

    Raises:
        ValueError: If portal_name is specified but not found.
    """
    with db_connection() as conn:
        if portal_name:
            portal = get_portal_by_name(conn, portal_name)
            if portal is None:
                raise ValueError(f"Portal not found: {portal_name}")
            portals = [portal]
        else:
            portals = get_enabled_portals(conn)

        logger.info("Running pipeline for %d portals", len(portals))

        results = {}
        for portal in portals:
            logger.info(
                "--- Processing portal: %s (%s) ---", portal.name, portal.url
            )
            stats = await process_portal(conn, portal)
            results[portal.name] = stats

        # Log summary
        total_found = sum(r.get("found", 0) for r in results.values())
        total_new = sum(r.get("new", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        errors = sum(1 for r in results.values() if "error" in r)

        logger.info(
            "Pipeline complete: %d portals, %d found, %d new, %d updated, %d errors",
            len(results),
            total_found,
            total_new,
            total_updated,
            errors,
        )

        return results
