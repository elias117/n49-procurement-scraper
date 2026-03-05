#!/usr/bin/env python3
"""
Firecrawl Agent scraper for n49 Procurement Platform.

Uses Firecrawl's agentic extraction to navigate procurement portals
and extract structured tender opportunity data.

Pilot: 4 portals. Free tier (5 credits/day).
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.keywords import load_keywords

logger = logging.getLogger("scraper.firecrawl_agent")
AGENT_TIMEOUT_SECONDS = 300

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TenderOpportunity(BaseModel):
    tender_title: Optional[str] = None
    description: Optional[str] = None
    closing_date: Optional[str] = None
    contract_value: Optional[str] = None
    solicitation_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    source_url: Optional[str] = None
    source_site: Optional[str] = None
    province: Optional[str] = None


class ExtractSchema(BaseModel):
    tender_opportunities: list[TenderOpportunity] = Field(
        ..., description="List of active tender opportunities."
    )


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------


def get_api_key() -> str:
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", "firecrawl.api.key", "-a", "clawbot", "-w"]
    ).decode().strip()


# ---------------------------------------------------------------------------
# Credit usage check
# ---------------------------------------------------------------------------


def check_credit_usage(api_key: str) -> dict:
    """Check current Firecrawl credit usage via API."""
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get("https://api.firecrawl.dev/v1/team/credit-usage", headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        logger.warning(f"Credit check failed: {r.status_code} {r.text}")
        return {"error": r.text, "status_code": r.status_code}


# ---------------------------------------------------------------------------
# Single portal run
# ---------------------------------------------------------------------------


def run_portal(app: FirecrawlApp, portal_name: str, portal_url: str, keywords_str: str) -> dict:
    """Run Firecrawl agent against one portal. Returns result dict."""
    logger.info(f"[{portal_name}] Starting agent run - {portal_url}")
    start = datetime.utcnow()

    try:
        result = app.agent(
            schema=ExtractSchema,
            prompt=(
                f"Extract active tender opportunities related to: {keywords_str}. "
                f"Include tender titles, descriptions, closing dates, contract values, "
                f"solicitation numbers, and all contact information for procurement officers."
            ),
            urls=[portal_url],
            model="spark-1-mini",
            timeout=AGENT_TIMEOUT_SECONDS,
        )

        elapsed = (datetime.utcnow() - start).total_seconds()

        # Extract data from result
        # result may be dict or Pydantic model depending on SDK version
        if hasattr(result, "data"):
            data = result.data
        elif isinstance(result, dict):
            data = result.get("data", result)
        else:
            data = result

        # Parse tender list
        if isinstance(data, dict) and "tender_opportunities" in data:
            tenders = data["tender_opportunities"]
        elif hasattr(data, "tender_opportunities"):
            tenders = data.tender_opportunities
        else:
            # Try to find nested data
            tenders = []
            logger.warning(f"[{portal_name}] Unexpected result shape: {type(data)}")

        # Normalize to dicts
        tender_dicts = []
        for t in tenders:
            if hasattr(t, "dict"):
                tender_dicts.append(t.dict())
            elif isinstance(t, dict):
                tender_dicts.append(t)

        logger.info(f"[{portal_name}] Done in {elapsed:.1f}s - {len(tender_dicts)} tenders")

        return {
            "portal": portal_name,
            "url": portal_url,
            "status": "success",
            "elapsed_seconds": elapsed,
            "listing_count": len(tender_dicts),
            "tenders": tender_dicts,
            "raw_result": str(result)[:500],  # truncated for logging
        }

    except Exception as e:
        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.error(f"[{portal_name}] FAILED after {elapsed:.1f}s: {e}", exc_info=True)
        return {
            "portal": portal_name,
            "url": portal_url,
            "status": "error",
            "elapsed_seconds": elapsed,
            "listing_count": 0,
            "tenders": [],
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Main pilot entrypoint
# ---------------------------------------------------------------------------

PILOT_PORTALS = [
    ("CanadaBuys", "https://canadabuys.canada.ca/en/tender-opportunities"),
    ("Halifax BidsAndTenders", "https://halifax.bidsandtenders.ca/"),
    ("MERX Ottawa", "https://www.merx.com/cityofottawa"),
    ("SEAO", "https://www.seao.ca/"),
]


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    api_key = get_api_key()
    app = FirecrawlApp(api_key=api_key)
    keywords = load_keywords()
    keywords_str = ", ".join(keywords[:50])  # cap at 50 to keep prompt manageable

    logger.info(f"Loaded {len(keywords)} keywords, using first 50 in prompt")
    logger.info(f"Pilot portals: {[p[0] for p in PILOT_PORTALS]}")

    # Check credits BEFORE runs
    credits_before = check_credit_usage(api_key)
    logger.info(f"Credits before: {credits_before}")

    results = []

    for portal_name, portal_url in PILOT_PORTALS:
        result = run_portal(app, portal_name, portal_url, keywords_str)
        results.append(result)

        # Log sample tender
        if result["tenders"]:
            sample = result["tenders"][0]
            logger.info(f"[{portal_name}] Sample tender: {json.dumps(sample, indent=2, default=str)[:300]}")

    # Check credits AFTER all runs
    credits_after = check_credit_usage(api_key)
    logger.info(f"Credits after: {credits_after}")

    # Summary report
    print("\n" + "=" * 60)
    print("FIRECRAWL PILOT RESULTS")
    print("=" * 60)

    total_listings = 0
    for r in results:
        status_icon = "OK" if r["status"] == "success" else "ERR"
        print(f"{status_icon} {r['portal']}: {r['listing_count']} listings in {r['elapsed_seconds']:.1f}s")
        if r.get("error"):
            print(f"   Error: {r['error'][:100]}")
        total_listings += r["listing_count"]

    print(f"\nTotal listings extracted: {total_listings}")
    print(f"\nCredits before: {json.dumps(credits_before, indent=2)}")
    print(f"Credits after:  {json.dumps(credits_after, indent=2)}")

    # Save full results to file
    output_path = Path("/tmp/firecrawl-pilot-results.json")
    with open(output_path, "w") as f:
        json.dump(
            {
                "run_at": datetime.utcnow().isoformat(),
                "portals_run": len(PILOT_PORTALS),
                "credits_before": credits_before,
                "credits_after": credits_after,
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )

    print(f"\nFull results saved to: {output_path}")
    return results, credits_before, credits_after


if __name__ == "__main__":
    main()
