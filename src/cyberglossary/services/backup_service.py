"""Database backup and restore.

Backup uses SQLite's backup API for a consistent snapshot (safe under WAL). Restore
validates the candidate first, always creates a safety backup of the current database,
then atomically replaces the database file and returns a fresh connection.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cyberglossary.database import connection, fts, migrations

REQUIRED_TABLES = {
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


class BackupError(Exception):
    """Raised when a backup or restore cannot be completed safely."""


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def unique_backup_name(directory: Path, base_name: str = "cyberglossary") -> str:
    """Return a non-colliding timestamped backup filename."""
    stamp = _timestamp()
    candidate = f"{base_name}-{stamp}.db"
    counter = 1
    while (directory / candidate).exists():
        counter += 1
        candidate = f"{base_name}-{stamp}-{counter}.db"
    return candidate


def verify_database(path: Path) -> None:
    """Validate that a file is a usable adudu database (raises BackupError)."""
    if not Path(path).is_file():
        raise BackupError(f"File not found: {path}")

    conn = sqlite3.connect(str(path))
    try:
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"Not a valid SQLite database: {exc}") from exc
        if row is None or row[0] != "ok":
            raise BackupError(f"Database integrity check failed: {row[0] if row else '?'}")

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            raise BackupError("Not a valid adudu database (no schema version)")

        existing = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - existing
        if missing:
            raise BackupError(f"Missing required tables: {sorted(missing)}")
    finally:
        conn.close()


def _replace_db_file(db_path: Path, source_path: Path) -> None:
    """Atomically replace the database file (connection must already be closed)."""
    tmp = db_path.with_name(db_path.name + ".restore-tmp")
    shutil.copy2(source_path, tmp)
    os.replace(tmp, db_path)
    for suffix in ("-wal", "-shm"):
        leftover = db_path.with_name(db_path.name + suffix)
        if leftover.exists():
            try:
                leftover.unlink()
            except OSError:
                pass


class BackupService:
    def __init__(self, conn: sqlite3.Connection, db_path: Path | str):
        self._conn = conn
        self._db_path = Path(db_path)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def create_backup(self, dest_dir: Path | str | None = None, base_name: str = "cyberglossary") -> Path:
        dest_dir = Path(dest_dir) if dest_dir else self._db_path.parent / "backups"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / unique_backup_name(dest_dir, base_name)

        dest = sqlite3.connect(str(dest_path))
        try:
            self._conn.backup(dest)
        finally:
            dest.close()

        verify_database(dest_path)
        return dest_path

    def restore(self, backup_path: Path | str, safety_dir: Path | str | None = None) -> sqlite3.Connection:
        backup_path = Path(backup_path)
        verify_database(backup_path)

        safety_dir = Path(safety_dir) if safety_dir else self._db_path.parent / "backups"
        # A safety backup of the current DB must succeed before any destructive step.
        self.create_backup(safety_dir, base_name="pre-restore")

        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._conn.close()

        _replace_db_file(self._db_path, backup_path)

        new_conn = connection.connect(self._db_path)
        migrations.migrate(new_conn)
        fts.ensure_index(new_conn)
        return new_conn
