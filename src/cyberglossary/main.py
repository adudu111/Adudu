"""CyberGlossary application entrypoint.

With no arguments this launches the PySide6 desktop UI. ``--init-db`` initializes the
local SQLite database and exits.
"""

from __future__ import annotations

import argparse
import sys

from cyberglossary.config import paths
from cyberglossary.database import connection, migrations


def init_database(db_path: str | None = None) -> tuple[int, str]:
    """Ensure the data directory exists, open the DB, and migrate to the latest schema."""
    paths.ensure_dirs()
    target = db_path or str(paths.database_path())
    conn = connection.connect(target)
    try:
        version = migrations.migrate(conn)
    finally:
        conn.close()
    return version, target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cyberglossary", description="adudu")
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="initialize the local database (creates it on first run) and exit",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="override the database file path (useful for development/testing)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.init_db:
        version, target = init_database(args.db_path)
        print(f"adudu database initialized: {target} (schema v{version})")
        return 0

    from cyberglossary.app import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
