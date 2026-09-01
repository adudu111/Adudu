"""Application data directory resolution.

All persistent application data lives under a single per-user directory that follows
Windows conventions:

    %APPDATA%\\CyberGlossary\\

The directory can be overridden via the ``CYBERGLOSSARY_DATA_DIR`` environment variable,
which is useful for development and testing (tests point this at a temporary directory).
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "CyberGlossary"
DATA_DIR_ENV_VAR = "CYBERGLOSSARY_DATA_DIR"

DB_FILENAME = "cyberglossary.db"
SETTINGS_FILENAME = "settings.json"
BACKUPS_DIR_NAME = "backups"


def app_data_dir() -> Path:
    """Return the root application data directory (created lazily by ``ensure_dirs``).

    Resolved from ``USERPROFILE`` (never virtualized) so the packaged app and source
    runs always use the same stable location — Store-Python processes silently redirect
    ``%APPDATA%`` to a package-private ``LocalCache`` folder, which must be avoided.
    """
    override = os.environ.get(DATA_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser()

    profile = os.environ.get("USERPROFILE") or Path.home()
    return Path(profile) / "AppData" / "Roaming" / APP_DIR_NAME


def database_path() -> Path:
    """Return the path to the SQLite database file."""
    return app_data_dir() / DB_FILENAME


def settings_path() -> Path:
    """Return the path to the application settings JSON file."""
    return app_data_dir() / SETTINGS_FILENAME


def backups_dir() -> Path:
    """Return the path to the backups directory."""
    return app_data_dir() / BACKUPS_DIR_NAME


def ensure_dirs() -> Path:
    """Create the application data directory tree and return its root."""
    root = app_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    backups_dir().mkdir(parents=True, exist_ok=True)
    return root
