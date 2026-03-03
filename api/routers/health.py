"""Health check endpoint."""
from fastapi import APIRouter
from api.db import get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Return API health status and DB connectivity."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM listings")
            count = cur.fetchone()[0]
        return {"status": "healthy", "listings_count": count}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
    finally:
        if conn is not None:
            conn.close()
