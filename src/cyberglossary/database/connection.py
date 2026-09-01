"""SQLite connection management.

Centralizes the connection options every part of the app must use: WAL journal mode,
enforced foreign keys, a busy timeout, and dict-like ``sqlite3.Row`` access.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Wait up to ~5s for a locked database (WAL readers/writers) before failing.
BUSY_TIMEOUT_MS = 5000


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection with the project's standard pragmas."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return conn
