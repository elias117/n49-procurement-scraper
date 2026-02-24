#!/usr/bin/env python3
"""Procurement scraper pipeline CLI.

Usage:
  python main.py                       # Run all enabled portals
  python main.py --portal CanadaBuys   # Run single portal by name
  python main.py --list-portals        # List all portals with enabled status
"""

import argparse
import asyncio
import logging
import os
import sys
import time

# Ensure the parent directory is on sys.path so that `scraper` package
# can be imported when this file is run directly (e.g., `python main.py`
# from within the scraper/ directory, as Docker CMD does).
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from scraper.config import LOG_LEVEL
from scraper.pipeline.orchestrator import run_pipeline

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scraper.main")


def list_portals():
    """Print all portals with their enabled status."""
    from scraper.db import get_connection

    import psycopg2.extras

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT name, url, level, province, enabled "
                "FROM portals ORDER BY level, province, name"
            )
            rows = cur.fetchall()
        print(
            f"\n{'Name':<40} {'Level':<12} {'Province':<25} "
            f"{'Enabled':<8} URL"
        )
        print("-" * 130)
        for r in rows:
            enabled = "YES" if r["enabled"] else "no"
            province = r["province"] or "-"
            print(
                f"{r['name']:<40} {r['level']:<12} {province:<25} "
                f"{enabled:<8} {r['url']}"
            )
        print(
            f"\nTotal: {len(rows)} portals "
            f"({sum(1 for r in rows if r['enabled'])} enabled)"
        )
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Procurement scraper pipeline"
    )
    parser.add_argument(
        "--portal", type=str, help="Run single portal by name"
    )
    parser.add_argument(
        "--list-portals",
        action="store_true",
        help="List all portals with enabled status",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation (useful when OpenAI quota is unavailable)",
    )
    args = parser.parse_args()

    if args.list_portals:
        list_portals()
        return

    start = time.time()
    logger.info("=" * 60)
    logger.info("PROCUREMENT SCRAPER PIPELINE STARTING")
    logger.info("=" * 60)

    try:
        results = asyncio.run(
            run_pipeline(
                portal_name=args.portal,
                skip_embeddings=args.skip_embeddings,
            )
        )
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        sys.exit(1)

    elapsed = time.time() - start

    # Print summary
    total_found = sum(r.get("found", 0) for r in results.values())
    total_new = sum(r.get("new", 0) for r in results.values())
    total_updated = sum(r.get("updated", 0) for r in results.values())
    errors = sum(1 for r in results.values() if "error" in r)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Portals processed: %d", len(results))
    logger.info("  Listings found: %d", total_found)
    logger.info("  New listings: %d", total_new)
    logger.info("  Updated listings: %d", total_updated)
    logger.info("  Portal errors: %d", errors)
    logger.info("  Duration: %.1fs", elapsed)
    logger.info("=" * 60)

    if errors > 0:
        logger.warning("%d portal(s) had errors -- check logs above", errors)

    # Exit with error code only if ALL portals failed
    if errors == len(results) and len(results) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
