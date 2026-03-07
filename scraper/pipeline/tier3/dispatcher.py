"""Dispatcher for Tier 3 city-specific scrapers."""

from __future__ import annotations

import logging

from scraper.models import PortalRecord, ProcurementListing
from scraper.pipeline.tier3.montreal import montreal_scrape
from scraper.pipeline.tier3.vancouver import vancouver_scrape
from scraper.pipeline.tier3.windsor import windsor_scrape

logger = logging.getLogger(__name__)


def classify_tier3_portal(portal: PortalRecord) -> str | None:
    """Classify a Tier 3 portal by URL."""
    url = portal.url.lower()

    if "citywindsor.ca" in url or "opendata.citywindsor.ca" in url:
        return "windsor"
    if "bids.vancouver.ca" in url:
        return "vancouver"
    if "montreal.ca" in url:
        return "montreal"

    return None


async def tier3_scrape(portal: PortalRecord) -> list[ProcurementListing]:
    """Dispatch to a city-specific Tier 3 scraper."""
    portal_type = classify_tier3_portal(portal)

    if portal_type == "windsor":
        return await windsor_scrape(portal)
    if portal_type == "vancouver":
        return await vancouver_scrape(portal)
    if portal_type == "montreal":
        return await montreal_scrape(portal)

    logger.warning("Portal '%s': no Tier 3 scraper matched URL %s", portal.name, portal.url)
    return []
