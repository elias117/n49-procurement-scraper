"""
Database helpers for the scraper pipeline.

Provides connection management, listing upsert (SCRP-06), portal queries,
and scrape run audit helpers. All SQL uses parameterized queries (%s style).
"""

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

from scraper import config
from scraper.models import ListingRecord, PortalRecord

logger = logging.getLogger("scraper.db")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


def get_connection():
    """
    Create a new database connection using DATABASE_URL from config.

    Returns a psycopg2 connection with autocommit=False.
    Caller is responsible for commit/rollback/close.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = False
    return conn


@contextmanager
def db_connection():
    """
    Context manager that yields a database connection.

    Commits on success, rolls back on exception, always closes.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Portal queries
# ---------------------------------------------------------------------------


def get_enabled_portals(conn) -> list:
    """
    Fetch all enabled portals, ordered by name.

    Returns list of PortalRecord.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, name, url, level, province, language, requires_login, enabled "
            "FROM portals WHERE enabled = true ORDER BY name"
        )
        rows = cur.fetchall()
    return [
        PortalRecord(
            id=str(row["id"]),
            name=row["name"],
            url=row["url"],
            level=row["level"],
            province=row.get("province"),
            language=row["language"],
            requires_login=row["requires_login"],
            enabled=row["enabled"],
        )
        for row in rows
    ]


def get_portal_by_name(conn, name: str) -> Optional[PortalRecord]:
    """
    Look up a single portal by name.

    Returns PortalRecord or None if not found.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, name, url, level, province, language, requires_login, enabled "
            "FROM portals WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return PortalRecord(
        id=str(row["id"]),
        name=row["name"],
        url=row["url"],
        level=row["level"],
        province=row.get("province"),
        language=row["language"],
        requires_login=row["requires_login"],
        enabled=row["enabled"],
    )


def disable_portal(conn, portal_id: str) -> None:
    """
    Disable a portal by setting enabled=false.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE portals SET enabled = false, updated_at = NOW() WHERE id = %s",
            (portal_id,),
        )


def check_auto_disable(conn, portal_id: str) -> bool:
    """
    Check the last N scrape runs for a portal. If all have status='failed',
    disable the portal.

    N is determined by PORTAL_CONSECUTIVE_FAILURE_THRESHOLD (default 5).
    Returns True if the portal was disabled, False otherwise.
    """
    threshold = config.PORTAL_CONSECUTIVE_FAILURE_THRESHOLD

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT status FROM scrape_runs "
            "WHERE portal_id = %s "
            "ORDER BY started_at DESC "
            "LIMIT %s",
            (portal_id, threshold),
        )
        rows = cur.fetchall()

    # Need at least `threshold` runs to trigger auto-disable
    if len(rows) < threshold:
        return False

    all_failed = all(row["status"] == "failed" for row in rows)
    if all_failed:
        disable_portal(conn, portal_id)
        config.logger.warning(
            "Auto-disabled portal %s after %d consecutive failures",
            portal_id,
            threshold,
        )
        return True

    return False


# ---------------------------------------------------------------------------
# Listing upsert (SCRP-06)
# ---------------------------------------------------------------------------

# SQL for upserting listings on the (source_portal, source_listing_id) composite key.
# Uses a CTE with RETURNING to distinguish new vs updated rows.
UPSERT_SQL = """
WITH input_rows(
    source_portal, source_listing_id, title, description, status,
    language, posting_date, closing_date, amended_date,
    province, raw_location, classification_codes,
    value_min, value_max, contact_info, documents,
    source_url, embedding, embedding_model, completeness_score
) AS (
    VALUES %s
),
upserted AS (
    INSERT INTO listings (
        source_portal, source_listing_id, title, description, status,
        language, posting_date, closing_date, amended_date,
        province, raw_location, classification_codes,
        value_min, value_max, contact_info, documents,
        source_url, embedding, embedding_model, completeness_score,
        last_scraped_at, created_at, updated_at
    )
    SELECT
        source_portal::uuid, source_listing_id, title, description,
        COALESCE(status, 'open'), language,
        posting_date::timestamptz, closing_date::timestamptz,
        amended_date::timestamptz,
        province, raw_location, classification_codes::jsonb,
        value_min::numeric, value_max::numeric, contact_info::jsonb, documents::jsonb,
        source_url, embedding::vector, embedding_model, completeness_score::numeric,
        NOW(), NOW(), NOW()
    FROM input_rows
    ON CONFLICT (source_portal, source_listing_id) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        status = COALESCE(EXCLUDED.status, listings.status),
        language = EXCLUDED.language,
        posting_date = EXCLUDED.posting_date,
        closing_date = EXCLUDED.closing_date,
        amended_date = EXCLUDED.amended_date,
        province = EXCLUDED.province,
        raw_location = EXCLUDED.raw_location,
        classification_codes = EXCLUDED.classification_codes,
        value_min = EXCLUDED.value_min,
        value_max = EXCLUDED.value_max,
        contact_info = EXCLUDED.contact_info,
        documents = EXCLUDED.documents,
        source_url = EXCLUDED.source_url,
        embedding = EXCLUDED.embedding,
        embedding_model = EXCLUDED.embedding_model,
        completeness_score = EXCLUDED.completeness_score,
        last_scraped_at = NOW(),
        updated_at = NOW(),
        revision = listings.revision + 1
    RETURNING id, (xmax = 0) AS is_new
)
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_new) AS new_count,
    COUNT(*) FILTER (WHERE NOT is_new) AS updated_count
FROM upserted;
"""


def _listing_to_tuple(listing: ListingRecord) -> tuple:
    """
    Convert a ListingRecord to a tuple of values for the upsert SQL.

    JSONB fields are wrapped with psycopg2.extras.Json().
    Embedding vectors are formatted as a string '[0.1, 0.2, ...]' for pgvector.
    """
    # Format embedding as string for pgvector compatibility
    embedding_str = None
    if listing.embedding is not None:
        embedding_str = "[" + ",".join(str(v) for v in listing.embedding) + "]"

    return (
        listing.source_portal,
        listing.source_listing_id,
        listing.title,
        listing.description,
        listing.status,
        listing.language,
        listing.posting_date,
        listing.closing_date,
        listing.amended_date,
        listing.province,
        listing.raw_location,
        psycopg2.extras.Json(listing.classification_codes)
        if listing.classification_codes is not None
        else None,
        listing.value_min,
        listing.value_max,
        psycopg2.extras.Json(listing.contact_info)
        if listing.contact_info is not None
        else None,
        psycopg2.extras.Json(listing.documents)
        if listing.documents is not None
        else None,
        listing.source_url,
        embedding_str,
        listing.embedding_model,
        listing.completeness_score,
    )


def upsert_listings(conn, portal_id: str, listings: list) -> dict:
    """
    Upsert a list of ListingRecord objects into the listings table.

    Uses ON CONFLICT (source_portal, source_listing_id) DO UPDATE to handle
    idempotent writes. Increments revision on update.

    Args:
        conn: psycopg2 connection
        portal_id: UUID string of the source portal (used for logging only;
                    each ListingRecord carries its own source_portal)
        listings: list of ListingRecord objects

    Returns:
        dict with keys: found, new, updated
    """
    if not listings:
        return {"found": 0, "new": 0, "updated": 0}

    values = [_listing_to_tuple(listing) for listing in listings]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # execute_values with fetch=True returns results directly.
        # With paging, each page runs the CTE separately, so we sum across pages.
        rows = psycopg2.extras.execute_values(
            cur,
            UPSERT_SQL,
            values,
            template=(
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            page_size=1000,
            fetch=True,
        )

    total = sum(int(r["total"]) for r in rows)
    new_count = sum(int(r["new_count"]) for r in rows)
    updated_count = sum(int(r["updated_count"]) for r in rows)

    return {
        "found": total,
        "new": new_count,
        "updated": updated_count,
    }


# ---------------------------------------------------------------------------
# Cross-portal dedup
# ---------------------------------------------------------------------------

# Remove duplicate listings that appear across different portals by comparing
# normalized titles (case/punctuation/spacing-insensitive).
CROSS_PORTAL_DEDUP_SQL = """
WITH normalized AS (
    SELECT
        id,
        source_portal,
        NULLIF(BTRIM(source_url), '') AS source_url,
        COALESCE(completeness_score, 0) AS completeness_score,
        updated_at,
        regexp_replace(lower(BTRIM(title)), '[^a-z0-9]+', '', 'g') AS normalized_title
    FROM listings
    WHERE title IS NOT NULL
),
cross_portal_groups AS (
    SELECT normalized_title
    FROM normalized
    WHERE normalized_title <> ''
    GROUP BY normalized_title
    HAVING count(DISTINCT source_portal) > 1
),
ranked AS (
    SELECT
        n.id,
        row_number() OVER (
            PARTITION BY n.normalized_title
            ORDER BY
                (n.source_url IS NOT NULL) DESC,
                n.completeness_score DESC,
                n.updated_at DESC,
                n.id
        ) AS rn,
        n.normalized_title
    FROM normalized AS n
    JOIN cross_portal_groups AS g
      ON g.normalized_title = n.normalized_title
),
to_delete AS (
    SELECT id
    FROM ranked
    WHERE rn > 1
)
DELETE FROM listings AS l
USING to_delete AS d
WHERE l.id = d.id;
"""


def deduplicate_cross_portal_listings(conn) -> int:
    """
    Remove cross-portal duplicate listings with near-identical titles.

    Keeps one "best" row per normalized title, preferring:
    1) non-empty source_url
    2) higher completeness_score
    3) most recently updated

    Returns:
        Number of rows deleted.
    """
    with conn.cursor() as cur:
        cur.execute(CROSS_PORTAL_DEDUP_SQL)
        try:
            removed = int(cur.rowcount or 0)
        except (TypeError, ValueError):
            removed = 0

    return removed if removed > 0 else 0


# ---------------------------------------------------------------------------
# Scrape run helpers
# ---------------------------------------------------------------------------


def start_scrape_run(conn, portal_id: str) -> str:
    """
    Insert a new scrape_runs row with status='running'.

    Returns the UUID of the new run as a string.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO scrape_runs (portal_id, started_at, status) "
            "VALUES (%s, NOW(), 'running') RETURNING id",
            (portal_id,),
        )
        row = cur.fetchone()
    return str(row[0])


def complete_scrape_run(conn, run_id: str, stats: dict) -> None:
    """
    Mark a scrape run as completed with listing stats.

    Args:
        conn: psycopg2 connection
        run_id: UUID string of the scrape run
        stats: dict with keys: found, new, updated
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE scrape_runs SET "
            "status = 'completed', "
            "completed_at = NOW(), "
            "listings_found = %s, "
            "listings_new = %s, "
            "listings_updated = %s, "
            "duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at)) "
            "WHERE id = %s",
            (
                stats.get("found", 0),
                stats.get("new", 0),
                stats.get("updated", 0),
                run_id,
            ),
        )


def fail_scrape_run(conn, run_id: str, error_message: str) -> None:
    """
    Mark a scrape run as failed with an error message.

    Args:
        conn: psycopg2 connection
        run_id: UUID string of the scrape run
        error_message: Description of what went wrong
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE scrape_runs SET "
            "status = 'failed', "
            "completed_at = NOW(), "
            "error_message = %s, "
            "duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at)) "
            "WHERE id = %s",
            (error_message, run_id),
        )


# ---------------------------------------------------------------------------
# Keyword purge (PURG-01, PURG-02)
# ---------------------------------------------------------------------------


def purge_unmatched_listings(conn, keywords: list) -> int:
    """
    Delete all listings that don't match any keyword on title or description.

    Uses the same matches_keywords() function as the scraper filter (PURG-02)
    to ensure consistent matching logic.

    Args:
        conn: psycopg2 connection (caller manages transaction).
        keywords: List of lowercased keyword strings.

    Returns:
        Number of listings deleted.
    """
    from scraper.pipeline.keywords import matches_keywords

    with conn.cursor() as cur:
        cur.execute("SELECT id, title, description FROM listings")
        rows = cur.fetchall()

    to_delete = [
        row[0] for row in rows
        if not matches_keywords(row[1], row[2], keywords)
    ]

    if not to_delete:
        logger.info("Purge: all %d listings match keywords, nothing to delete", len(rows))
        return 0

    deleted = 0
    batch_size = 1000
    with conn.cursor() as cur:
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i:i + batch_size]
            cur.execute("DELETE FROM listings WHERE id = ANY(%s::uuid[])", (batch,))
            deleted += cur.rowcount

    logger.info(
        "Purge: deleted %d non-matching listings out of %d total",
        deleted, len(rows),
    )
    return deleted
