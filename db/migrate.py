#!/usr/bin/env python3
"""
Database migration runner.

Reads SQL files from db/migrations/, tracks applied migrations in a
schema_migrations table, and runs any pending migrations in filename order.

Usage:
    python db/migrate.py                    # Apply pending migrations
    python db/migrate.py --status           # Show migration status
    python db/migrate.py --dry-run          # Show what would run without executing
    python db/migrate.py --mark-applied     # Mark all migrations as applied without running

Environment:
    DATABASE_URL    PostgreSQL connection string (required)

Exit codes:
    0   All migrations applied (or nothing to do)
    1   Migration failed (rolls back the failed migration only)
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [migrate] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate")

# Resolve migrations directory relative to this script.
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Pattern: filenames must start with digits (e.g., 001_, 002_, 010_).
MIGRATION_PATTERN = re.compile(r"^\d+.*\.sql$")


def get_connection(database_url: str | None = None):
    """Create a database connection from DATABASE_URL."""
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL is not set")
        sys.exit(1)
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def ensure_tracking_table(conn) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id          SERIAL PRIMARY KEY,
                filename    VARCHAR(500) NOT NULL UNIQUE,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                checksum    VARCHAR(64)
            )
        """)
    conn.commit()


def get_applied_migrations(conn) -> set[str]:
    """Return the set of filenames already applied."""
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations ORDER BY filename")
        return {row[0] for row in cur.fetchall()}


def discover_migrations() -> list[Path]:
    """
    Find all .sql files in the migrations directory, sorted by filename.

    Only files matching the MIGRATION_PATTERN (starting with digits) are
    included. This excludes READMEs, backups, etc.
    """
    if not MIGRATIONS_DIR.is_dir():
        logger.error("Migrations directory not found: %s", MIGRATIONS_DIR)
        sys.exit(1)

    files = sorted(
        f
        for f in MIGRATIONS_DIR.iterdir()
        if f.is_file() and MIGRATION_PATTERN.match(f.name)
    )
    return files


def file_checksum(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_migration(conn, path: Path) -> None:
    """
    Apply a single migration file inside a transaction.

    Reads the SQL, executes it, records the filename + checksum in
    schema_migrations, and commits. On failure, rolls back and re-raises.
    """
    sql = path.read_text(encoding="utf-8")
    checksum = file_checksum(path)

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                (path.name, checksum),
            )
        conn.commit()
        logger.info("  ✓ Applied: %s", path.name)
    except Exception:
        conn.rollback()
        raise


def mark_migration_applied(conn, path: Path) -> None:
    """Record a migration as applied without executing it."""
    checksum = file_checksum(path)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s) "
            "ON CONFLICT (filename) DO NOTHING",
            (path.name, checksum),
        )
    conn.commit()


def run_migrations(
    database_url: str | None = None,
    dry_run: bool = False,
    mark_applied: bool = False,
    status_only: bool = False,
) -> int:
    """
    Main entry point: discover, diff, and apply pending migrations.

    Args:
        database_url: Override DATABASE_URL.
        dry_run: Print what would run without executing.
        mark_applied: Mark all as applied without executing (baseline).
        status_only: Print migration status and exit.

    Returns:
        Number of migrations applied (or that would be applied).
    """
    conn = get_connection(database_url)
    try:
        ensure_tracking_table(conn)

        all_migrations = discover_migrations()
        applied = get_applied_migrations(conn)
        pending = [m for m in all_migrations if m.name not in applied]

        if status_only:
            logger.info("Migration status (%d total, %d applied, %d pending):",
                        len(all_migrations), len(applied), len(pending))
            for m in all_migrations:
                marker = "✓" if m.name in applied else "○"
                logger.info("  %s %s", marker, m.name)
            return len(pending)

        if not pending:
            logger.info("No pending migrations. Database is up to date.")
            return 0

        logger.info("%d pending migration(s):", len(pending))
        for m in pending:
            logger.info("  ○ %s", m.name)

        if dry_run:
            logger.info("Dry run — no changes made.")
            return len(pending)

        if mark_applied:
            logger.info("Marking all as applied (baseline mode)...")
            for m in pending:
                mark_migration_applied(conn, m)
                logger.info("  ✓ Marked: %s", m.name)
            return len(pending)

        # Apply pending migrations one at a time.
        applied_count = 0
        for m in pending:
            try:
                apply_migration(conn, m)
                applied_count += 1
            except Exception as e:
                logger.error("  ✗ FAILED: %s — %s", m.name, e)
                logger.error("Stopping migration runner. Fix the issue and re-run.")
                return -1

        logger.info("All %d migration(s) applied successfully.", applied_count)
        return applied_count

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Database migration runner")
    parser.add_argument(
        "--status", action="store_true",
        help="Show migration status without making changes",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show pending migrations without applying",
    )
    parser.add_argument(
        "--mark-applied", action="store_true",
        help="Mark all pending migrations as applied without running SQL (for baselining existing DBs)",
    )
    args = parser.parse_args()

    result = run_migrations(
        status_only=args.status,
        dry_run=args.dry_run,
        mark_applied=args.mark_applied,
    )

    if result == -1:
        sys.exit(1)


if __name__ == "__main__":
    main()
