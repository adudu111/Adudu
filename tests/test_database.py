"""Tests for database connection, migrations, and the canonical schema."""

from __future__ import annotations

import sqlite3

from cyberglossary.database import migrations
from cyberglossary.main import init_database

EXPECTED_TABLES = {
    "app_meta",
    "profiles",
    "categories",
    "tags",
    "terms",
    "aliases",
    "term_tags",
    "sections",
    "templates",
    "template_sections",
    "settings",
    "terms_fts",
}


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table')"
        ).fetchall()
    }


def test_migrate_creates_canonical_schema(conn):
    assert EXPECTED_TABLES <= table_names(conn)
    assert migrations.current_version(conn) == migrations.LATEST_VERSION


def test_migrate_is_idempotent(conn):
    first = migrations.migrate(conn)
    second = migrations.migrate(conn)
    assert first == second == migrations.LATEST_VERSION


def test_connection_enforces_foreign_keys_and_wal(conn):
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert fk == 1
    assert journal == "wal"


def test_fts_table_is_virtual(conn):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'terms_fts'"
    ).fetchone()
    assert row is not None
    assert row["sql"].upper().startswith("CREATE VIRTUAL TABLE")


def test_init_database_creates_file_and_is_idempotent(tmp_path):
    target = tmp_path / "app.db"
    version, path = init_database(db_path=str(target))
    assert version == migrations.LATEST_VERSION
    assert path == str(target)
    assert target.exists()

    # A second call should not error and should leave the version unchanged.
    version2, _ = init_database(db_path=str(target))
    assert version2 == migrations.LATEST_VERSION
