"""Listing detail endpoint."""
from __future__ import annotations

import decimal
import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
import psycopg2.extras

from api.db import db_connection

router = APIRouter(tags=["listings"])


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert UUID, datetime, and Decimal values to JSON-safe types."""
    result = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


@router.get("/listings/{listing_id}")
def get_listing(listing_id: str):
    """Return full detail for a single listing by ID."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT l.id, l.source_portal, l.source_listing_id, l.title,
                       l.description, l.status, l.language,
                       l.posting_date, l.closing_date, l.amended_date,
                       l.province, l.raw_location,
                       COALESCE(l.classification_codes, '[]'::jsonb) AS classification_codes,
                       l.value_min, l.value_max,
                       l.contact_info,
                       COALESCE(l.documents, '[]'::jsonb) AS documents,
                       l.revision, l.source_url,
                       l.last_scraped_at, l.created_at, l.updated_at,
                       p.name AS source_portal_name, p.url AS portal_url
                FROM listings l
                JOIN portals p ON l.source_portal = p.id
                WHERE l.id = %s
                """,
                (listing_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    return _serialize_row(dict(row))
