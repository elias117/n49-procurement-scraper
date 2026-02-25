"""User authentication and last-visit tracking endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import psycopg2.extras

from api.db import db_connection

router = APIRouter(tags=["users"])


@router.get("/auth/user")
def get_user_by_username(username: str = Query(..., description="Username to look up")):
    """Look up a user by username. Used by Next.js auth layer."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, name, password_hash, last_visited_at
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    result = dict(row)
    result["id"] = str(result["id"])
    if result.get("last_visited_at"):
        result["last_visited_at"] = result["last_visited_at"].isoformat()
    return result


@router.get("/users/{user_id}/last-visit")
def get_last_visit(user_id: str):
    """Return the user's last_visited_at timestamp."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT last_visited_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    result = dict(row)
    if result.get("last_visited_at"):
        result["last_visited_at"] = result["last_visited_at"].isoformat()
    return result


@router.put("/users/{user_id}/last-visit")
def update_last_visit(user_id: str):
    """Update the user's last_visited_at to NOW()."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE users
                SET last_visited_at = NOW()
                WHERE id = %s
                RETURNING last_visited_at
                """,
                (user_id,),
            )
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    result = dict(row)
    if result.get("last_visited_at"):
        result["last_visited_at"] = result["last_visited_at"].isoformat()
    return result
