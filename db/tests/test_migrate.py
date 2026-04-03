"""Tests for the database migration runner (db/migrate.py)."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# The migrate module is at db/migrate.py — adjust path for imports.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from db.migrate import (
    MIGRATION_PATTERN,
    apply_migration,
    discover_migrations,
    ensure_tracking_table,
    file_checksum,
    get_applied_migrations,
    mark_migration_applied,
    run_migrations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_migration_file(tmp_path: Path, name: str, content: str = "SELECT 1;") -> Path:
    """Create a migration file in a tmp directory."""
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


def _mock_conn():
    """Return a mock psycopg2 connection with cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor
    return conn, cursor


# ---------------------------------------------------------------------------
# MIGRATION_PATTERN
# ---------------------------------------------------------------------------

class TestMigrationPattern:
    """Filename pattern matching."""

    def test_matches_standard_names(self):
        assert MIGRATION_PATTERN.match("001_initial_schema.sql")
        assert MIGRATION_PATTERN.match("010_add_reference_number.sql")
        assert MIGRATION_PATTERN.match("999_final.sql")

    def test_rejects_non_numeric_prefix(self):
        assert not MIGRATION_PATTERN.match("README.md")
        assert not MIGRATION_PATTERN.match("backup_001.sql")
        assert not MIGRATION_PATTERN.match(".gitkeep")

    def test_rejects_non_sql_extension(self):
        assert not MIGRATION_PATTERN.match("001_schema.py")
        assert not MIGRATION_PATTERN.match("001_schema.txt")


# ---------------------------------------------------------------------------
# file_checksum
# ---------------------------------------------------------------------------

class TestFileChecksum:
    """SHA-256 checksum computation."""

    def test_deterministic(self, tmp_path):
        f = _make_migration_file(tmp_path, "001.sql", "CREATE TABLE t;")
        c1 = file_checksum(f)
        c2 = file_checksum(f)
        assert c1 == c2
        assert len(c1) == 64  # SHA-256 hex is 64 chars

    def test_different_content_different_checksum(self, tmp_path):
        f1 = _make_migration_file(tmp_path, "001.sql", "CREATE TABLE a;")
        f2 = _make_migration_file(tmp_path, "002.sql", "CREATE TABLE b;")
        assert file_checksum(f1) != file_checksum(f2)


# ---------------------------------------------------------------------------
# ensure_tracking_table
# ---------------------------------------------------------------------------

class TestEnsureTrackingTable:
    """Tracking table creation."""

    def test_creates_table(self):
        conn, cursor = _mock_conn()
        ensure_tracking_table(conn)
        # Should execute CREATE TABLE IF NOT EXISTS
        assert cursor.execute.called
        sql = cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS schema_migrations" in sql
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_applied_migrations
# ---------------------------------------------------------------------------

class TestGetAppliedMigrations:
    """Query applied migrations from tracking table."""

    def test_returns_set_of_filenames(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [
            ("001_initial.sql",),
            ("002_seed.sql",),
        ]
        result = get_applied_migrations(conn)
        assert result == {"001_initial.sql", "002_seed.sql"}

    def test_returns_empty_set_when_none_applied(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []
        result = get_applied_migrations(conn)
        assert result == set()


# ---------------------------------------------------------------------------
# discover_migrations
# ---------------------------------------------------------------------------

class TestDiscoverMigrations:
    """Filesystem migration discovery."""

    def test_finds_sql_files_sorted(self, tmp_path):
        _make_migration_file(tmp_path, "003_c.sql")
        _make_migration_file(tmp_path, "001_a.sql")
        _make_migration_file(tmp_path, "002_b.sql")
        _make_migration_file(tmp_path, "README.md")

        with patch("db.migrate.MIGRATIONS_DIR", tmp_path):
            result = discover_migrations()

        names = [f.name for f in result]
        assert names == ["001_a.sql", "002_b.sql", "003_c.sql"]

    def test_excludes_non_matching_files(self, tmp_path):
        _make_migration_file(tmp_path, "001_ok.sql")
        _make_migration_file(tmp_path, "backup.sql")
        _make_migration_file(tmp_path, ".gitkeep")

        with patch("db.migrate.MIGRATIONS_DIR", tmp_path):
            result = discover_migrations()

        assert len(result) == 1
        assert result[0].name == "001_ok.sql"

    def test_exits_if_directory_missing(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with patch("db.migrate.MIGRATIONS_DIR", missing):
            with pytest.raises(SystemExit):
                discover_migrations()


# ---------------------------------------------------------------------------
# apply_migration
# ---------------------------------------------------------------------------

class TestApplyMigration:
    """Single migration application."""

    def test_executes_sql_and_records(self, tmp_path):
        conn, cursor = _mock_conn()
        f = _make_migration_file(tmp_path, "001_test.sql", "CREATE TABLE t (id INT);")

        apply_migration(conn, f)

        # First call: execute the SQL
        calls = cursor.execute.call_args_list
        assert "CREATE TABLE t (id INT);" in calls[0][0][0]
        # Second call: INSERT into schema_migrations
        assert "INSERT INTO schema_migrations" in calls[1][0][0]
        assert calls[1][0][1][0] == "001_test.sql"
        conn.commit.assert_called_once()

    def test_rolls_back_on_failure(self, tmp_path):
        conn, cursor = _mock_conn()
        cursor.execute.side_effect = Exception("syntax error")
        f = _make_migration_file(tmp_path, "001_bad.sql", "INVALID SQL;")

        with pytest.raises(Exception, match="syntax error"):
            apply_migration(conn, f)

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# mark_migration_applied
# ---------------------------------------------------------------------------

class TestMarkMigrationApplied:
    """Mark-as-applied without executing SQL."""

    def test_inserts_record(self, tmp_path):
        conn, cursor = _mock_conn()
        f = _make_migration_file(tmp_path, "001_test.sql", "SELECT 1;")

        mark_migration_applied(conn, f)

        calls = cursor.execute.call_args_list
        assert "INSERT INTO schema_migrations" in calls[0][0][0]
        assert "ON CONFLICT" in calls[0][0][0]
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# run_migrations (integration-level with mocks)
# ---------------------------------------------------------------------------

class TestRunMigrations:
    """End-to-end migration runner logic."""

    def test_no_pending_returns_zero(self, tmp_path):
        """When all migrations are applied, returns 0."""
        _make_migration_file(tmp_path, "001_a.sql")
        _make_migration_file(tmp_path, "002_b.sql")

        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [("001_a.sql",), ("002_b.sql",)]

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            result = run_migrations(database_url="dummy")

        assert result == 0

    def test_applies_pending_migrations(self, tmp_path):
        """Pending migrations get applied in order."""
        _make_migration_file(tmp_path, "001_a.sql", "CREATE TABLE a;")
        _make_migration_file(tmp_path, "002_b.sql", "CREATE TABLE b;")
        _make_migration_file(tmp_path, "003_c.sql", "CREATE TABLE c;")

        conn, cursor = _mock_conn()
        # Only 001 is already applied.
        cursor.fetchall.return_value = [("001_a.sql",)]

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            result = run_migrations(database_url="dummy")

        assert result == 2
        # Verify commit was called: once for ensure_tracking_table + twice for 2 migrations
        assert conn.commit.call_count == 3

    def test_dry_run_no_changes(self, tmp_path):
        """Dry run returns pending count but doesn't execute."""
        _make_migration_file(tmp_path, "001_a.sql")
        _make_migration_file(tmp_path, "002_b.sql")

        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            result = run_migrations(database_url="dummy", dry_run=True)

        assert result == 2
        # Only one commit: ensure_tracking_table. No migration commits.
        assert conn.commit.call_count == 1

    def test_mark_applied_records_without_executing(self, tmp_path):
        """Mark-applied mode records filenames without running SQL."""
        _make_migration_file(tmp_path, "001_a.sql", "DROP TABLE everything;")

        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            result = run_migrations(database_url="dummy", mark_applied=True)

        assert result == 1
        # The dangerous SQL should NOT have been executed.
        # Only: CREATE TABLE IF NOT EXISTS (tracking), SELECT (get_applied), INSERT (mark)
        sql_calls = [c[0][0] for c in cursor.execute.call_args_list]
        assert not any("DROP TABLE" in s for s in sql_calls)

    def test_status_only_returns_pending_count(self, tmp_path):
        """Status mode returns pending count without applying."""
        _make_migration_file(tmp_path, "001_a.sql")
        _make_migration_file(tmp_path, "002_b.sql")
        _make_migration_file(tmp_path, "003_c.sql")

        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [("001_a.sql",)]

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            result = run_migrations(database_url="dummy", status_only=True)

        assert result == 2

    def test_stops_on_failure(self, tmp_path):
        """If a migration fails, runner stops and returns -1."""
        _make_migration_file(tmp_path, "001_ok.sql", "SELECT 1;")
        _make_migration_file(tmp_path, "002_bad.sql", "INVALID;")
        _make_migration_file(tmp_path, "003_never.sql", "SELECT 2;")

        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []

        # First migration succeeds, second fails
        call_count = [0]
        original_execute = cursor.execute

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # Calls: 1=CREATE TABLE, 2=SELECT applied, 3=execute 001 SQL,
            # 4=INSERT 001 record, 5=execute 002 SQL (should fail)
            if call_count[0] == 5:
                raise Exception("syntax error in 002")

        cursor.execute.side_effect = side_effect

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            result = run_migrations(database_url="dummy")

        assert result == -1

    def test_connection_closed_on_success(self, tmp_path):
        """Connection is always closed."""
        _make_migration_file(tmp_path, "001_a.sql")
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [("001_a.sql",)]

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            run_migrations(database_url="dummy")

        conn.close.assert_called_once()

    def test_connection_closed_on_failure(self, tmp_path):
        """Connection is closed even when a migration fails."""
        _make_migration_file(tmp_path, "001_a.sql")
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:  # execute migration SQL
                raise Exception("boom")

        cursor.execute.side_effect = side_effect

        with (
            patch("db.migrate.MIGRATIONS_DIR", tmp_path),
            patch("db.migrate.get_connection", return_value=conn),
        ):
            run_migrations(database_url="dummy")

        conn.close.assert_called_once()
