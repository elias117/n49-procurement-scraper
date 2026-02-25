"""Portal health and data freshness endpoints."""
from __future__ import annotations

from fastapi import APIRouter
import psycopg2.extras

from api.db import db_connection

router = APIRouter(tags=["health"])


@router.get("/health/portals")
def portal_health():
    """Per-portal health status with last 5 runs aggregation."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                WITH latest_runs AS (
                    SELECT
                        sr.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY sr.portal_id
                            ORDER BY sr.started_at DESC
                        ) AS rn
                    FROM scrape_runs sr
                ),
                portal_stats AS (
                    SELECT
                        lr.portal_id,
                        COUNT(*) FILTER (
                            WHERE lr.rn <= 5 AND lr.status = 'failed'
                        ) AS recent_failures,
                        COUNT(*) FILTER (
                            WHERE lr.rn <= 5
                        ) AS recent_total,
                        MAX(lr.completed_at) FILTER (
                            WHERE lr.status = 'completed'
                        ) AS last_success_at,
                        MAX(lr.started_at) AS last_run_at
                    FROM latest_runs lr
                    GROUP BY lr.portal_id
                )
                SELECT
                    p.id AS portal_id,
                    p.name,
                    p.url,
                    p.enabled,
                    ps.recent_failures,
                    ps.recent_total,
                    ps.last_success_at,
                    ps.last_run_at,
                    lr.status AS last_run_status,
                    lr.listings_found,
                    lr.listings_new,
                    lr.listings_updated,
                    lr.duration_seconds,
                    lr.error_message,
                    (SELECT COUNT(*) FROM listings WHERE source_portal = p.id)
                        AS total_listings
                FROM portals p
                LEFT JOIN portal_stats ps ON ps.portal_id = p.id
                LEFT JOIN latest_runs lr
                    ON lr.portal_id = p.id AND lr.rn = 1
                ORDER BY p.name
                """
            )
            rows = cur.fetchall()

    return [dict(row) for row in rows]


@router.get("/health/freshness")
def data_freshness():
    """Return the timestamp of the most recent completed scrape run."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT MAX(completed_at) AS last_updated
                FROM scrape_runs
                WHERE status = 'completed'
                """
            )
            row = cur.fetchone()

    return dict(row) if row else {"last_updated": None}
