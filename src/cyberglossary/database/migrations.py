"""Versioned schema migrations.

Schema version is tracked with SQLite's ``PRAGMA user_version`` (an integer stored in
the database header), which is simple, atomic, and readable by any tool. Migrations are
applied in order inside a transaction; each migration advances ``user_version``.

Migration scripts are loaded from ``schema.sql`` for v1; future schema changes append
new numbered migrations here rather than editing the v1 script.
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


def _load_schema() -> str:
    # Robust for both development and PyInstaller-frozen execution (never depends on CWD).
    path = Path(__file__).with_name("schema.sql")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return resources.files("cyberglossary.database").joinpath("schema.sql").read_text(
        encoding="utf-8"
    )


_SCHEMA_SQL = _load_schema()

# Ordered list of (version, SQL script). Version numbers are permanent and must never be
# reused or reordered. Add new entries at the end.
MIGRATIONS: list[tuple[int, str]] = [
    (1, _SCHEMA_SQL),
]

LATEST_VERSION = MIGRATIONS[-1][0] if MIGRATIONS else 0


def current_version(conn: sqlite3.Connection) -> int:
    """Return the currently applied schema version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(conn: sqlite3.Connection) -> int:
    """Apply any pending migrations and return the resulting schema version.

    Idempotent: running it against an already-current database applies nothing.
    """
    applied = current_version(conn)
    for version, script in MIGRATIONS:
        if version <= applied:
            continue
        # executescript issues an implicit COMMIT, so it must not run inside a
        # `with conn:` transaction block.
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
        applied = version
    return applied


def initialize(db_path: str | None = None) -> tuple[int, str]:
    """Create the database (if needed), migrate to the latest schema, and backfill FTS.

    Convenience wrapper used by the CLI entrypoint. Returns (version, path).
    """
    from cyberglossary.config import paths
    from cyberglossary.database import fts

    target = db_path or str(paths.database_path())
    conn = sqlite3.connect(target)
    try:
        version = migrate(conn)
        fts.ensure_index(conn)
    finally:
        conn.close()
    return version, target
