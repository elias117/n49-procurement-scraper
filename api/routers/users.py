"""User authentication and last-visit tracking endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
import psycopg2.extras
from pydantic import BaseModel, Field

from api.db import db_connection

router = APIRouter(tags=["users"])


class AuthVerifyRequest(BaseModel):
    """Credential payload for server-side password verification."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


@router.get("/auth/user")
def get_user_by_username(username: str = Query(..., description="Username to look up")):
    """Look up non-sensitive user fields by username."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, name, last_visited_at
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


@router.post("/auth/verify")
def verify_user_credentials(payload: AuthVerifyRequest):
    """Verify username/password without exposing password hashes."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, name, last_visited_at
                FROM users
                WHERE username = %s
                  AND password_hash = crypt(%s, password_hash)
                """,
                (payload.username, payload.password),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    result = dict(row)
    result["id"] = str(result["id"])
    if result.get("last_visited_at"):
        result["last_visited_at"] = result["last_visited_at"].isoformat()
    return result


@router.get("/users/{user_id}/last-visit")
def get_last_visit(user_id: UUID):
    """Return the user's last_visited_at timestamp."""
    with db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT last_visited_at FROM users WHERE id = %s",
                (str(user_id),),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    result = dict(row)
    if result.get("last_visited_at"):
        result["last_visited_at"] = result["last_visited_at"].isoformat()
    return result


@router.put("/users/{user_id}/last-visit")
def update_last_visit(user_id: UUID):
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
                (str(user_id),),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    result = dict(row)
    if result.get("last_visited_at"):
        result["last_visited_at"] = result["last_visited_at"].isoformat()
    return result
