"""Facet count queries for search result breakdowns.

Runs a single query returning province and portal facet counts
from the filtered result set (before pagination).
"""
from __future__ import annotations

from typing import List

import psycopg2.extras
from api.models.response import FacetCounts, FacetValue


def execute_facet_counts(
    conn, filter_clause: str, filter_params: dict
) -> FacetCounts:
    """Execute facet count query and return province/portal breakdowns.

    Args:
        conn: psycopg2 connection.
        filter_clause: Pre-built SQL WHERE fragment from build_filter_clause.
        filter_params: Parameter dict from build_filter_clause.

    Returns:
        FacetCounts with provinces and portals lists sorted by count DESC.
    """
    sql = f"""
WITH filtered AS (
    SELECT id, province, source_portal
    FROM listings
    WHERE {filter_clause}
),
province_facets AS (
    SELECT COALESCE(province, 'National') AS facet_value,
           COUNT(*) AS count
    FROM filtered
    GROUP BY COALESCE(province, 'National')
    ORDER BY count DESC
),
portal_facets AS (
    SELECT p.name AS facet_value, COUNT(*) AS count
    FROM filtered f
    JOIN portals p ON f.source_portal = p.id
    GROUP BY p.name
    ORDER BY count DESC
)
SELECT 'province' AS facet_type, facet_value, count FROM province_facets
UNION ALL
SELECT 'portal' AS facet_type, facet_value, count FROM portal_facets;
"""

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(sql, filter_params)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    provinces: List[FacetValue] = []
    portals: List[FacetValue] = []

    for row in rows:
        fv = FacetValue(value=row["facet_value"], count=row["count"])
        if row["facet_type"] == "province":
            provinces.append(fv)
        elif row["facet_type"] == "portal":
            portals.append(fv)

    return FacetCounts(provinces=provinces, portals=portals)
