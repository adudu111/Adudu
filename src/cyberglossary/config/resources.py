"""Application resource-path resolution (compatible with PyInstaller frozen apps)."""

from __future__ import annotations

import sys
from pathlib import Path


def application_root() -> Path:
    """Return the directory containing bundled resources.

    Frozen (PyInstaller onedir): ``<exe_dir>/_internal``. Development: the project root
    (the directory containing both ``src`` and ``packaging``).
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal = exe_dir / "_internal"
        return internal if internal.is_dir() else exe_dir

    current = Path(__file__).resolve().parent
    for parent in (current, *current.parents):
        if (parent / "src").is_dir() and (parent / "packaging").is_dir():
            return parent
    return current


def resource_path(relative: str) -> Path:
    """Return the absolute path to a bundled application resource."""
    return application_root() / relative


def web_dir() -> Path:
    """Return the bundled frontend directory (``index.html`` / ``app.js`` / ``qwebchannel.js``).

    Resolves correctly in BOTH modes:

    - Packaged (PyInstaller onedir): ``<exe_dir>/_internal/web``
    - Source run (``python -m cyberglossary``): ``src/cyberglossary/ui/web``
    """
    if getattr(sys, "frozen", False):
        return application_root() / "web"
    return Path(__file__).resolve().parent.parent / "ui" / "web"
