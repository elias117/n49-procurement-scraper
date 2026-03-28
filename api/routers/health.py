"""Health check endpoint."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from api.db import get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Return API health status and DB connectivity.

    Returns HTTP 200 when healthy, HTTP 503 when unhealthy.
    Deploy scripts and load balancers rely on the status code —
    returning 200 on failure masks production outages.
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM listings")
            count = cur.fetchone()[0]
        return {"status": "healthy", "listings_count": count}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )
    finally:
        if conn is not None:
            conn.close()
