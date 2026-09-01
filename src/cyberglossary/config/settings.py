"""Application settings: a small, JSON-backed, user-editable preferences store.

This is deliberately minimal. It holds application-level preferences that are
independent of the knowledge database (which lives in SQLite). The DB-scoped
``settings`` table inside SQLite is used for data-adjacent state such as the active
profile; this module is for UI/preferences such as theme and backup location.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from cyberglossary.config import paths

THEME_DARK = "dark"
THEME_LIGHT = "light"
THEME_SYSTEM = "system"
VALID_THEMES = (THEME_SYSTEM, THEME_DARK, THEME_LIGHT)


@dataclass
class AppSettings:
    """User-facing application preferences."""

    theme: str = THEME_DARK
    backup_dir: str | None = None
    lookup_paused: bool = False
    # Structured hotkey (Win32): bitmask of MOD_* + virtual-key code.
    # Defaults: MOD_CONTROL | MOD_SHIFT (6) and 'D' (0x44) → Ctrl+Shift+D.
    hotkey_modifiers: int = 6
    hotkey_key: int = 68

    # Launcher (global search) hotkey. Defaults: Ctrl+Shift+Space.
    launcher_hotkey_modifiers: int = 6
    launcher_hotkey_key: int = 0x20

    # Launcher recents/pins: ordered lists of term ids (JSON, no schema change).
    launcher_recent: list[int] = field(default_factory=list)
    launcher_pinned: list[int] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return a list of human-readable validation errors (empty means valid)."""
        errors: list[str] = []
        if self.theme not in VALID_THEMES:
            errors.append(f"theme must be one of {VALID_THEMES}, got {self.theme!r}")
        if self.backup_dir is not None and not isinstance(self.backup_dir, str):
            errors.append("backup_dir must be a string path or null")
        return errors


def _coerce_int_list(data: Any) -> list[int]:
    """Coerce a JSON value to a list of ints (ignoring anything non-integer)."""
    if not isinstance(data, list):
        return []
    return [int(x) for x in data if isinstance(x, int) and not isinstance(x, bool)]


def _coerce(data: dict[str, Any]) -> AppSettings:
    """Build an AppSettings from a raw dict, ignoring unknown keys."""
    settings = AppSettings()
    if "theme" in data and isinstance(data["theme"], str):
        settings.theme = data["theme"]
    if "backup_dir" in data:
        settings.backup_dir = data["backup_dir"] if isinstance(data["backup_dir"], str) else None
    if "lookup_paused" in data and isinstance(data["lookup_paused"], bool):
        settings.lookup_paused = data["lookup_paused"]
    if "hotkey_modifiers" in data and isinstance(data["hotkey_modifiers"], int):
        settings.hotkey_modifiers = data["hotkey_modifiers"]
    if "hotkey_key" in data and isinstance(data["hotkey_key"], int):
        settings.hotkey_key = data["hotkey_key"]
    if "launcher_hotkey_modifiers" in data and isinstance(data["launcher_hotkey_modifiers"], int):
        settings.launcher_hotkey_modifiers = data["launcher_hotkey_modifiers"]
    if "launcher_hotkey_key" in data and isinstance(data["launcher_hotkey_key"], int):
        settings.launcher_hotkey_key = data["launcher_hotkey_key"]
    settings.launcher_recent = _coerce_int_list(data.get("launcher_recent"))
    settings.launcher_pinned = _coerce_int_list(data.get("launcher_pinned"))
    return settings


def load(path: Path | None = None) -> AppSettings:
    """Load settings from disk, falling back to defaults on any problem."""
    target = path or paths.settings_path()
    if not target.exists():
        return AppSettings()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(raw, dict):
        return AppSettings()
    return _coerce(raw)


def save(settings: AppSettings, path: Path | None = None) -> Path:
    """Persist settings to disk, returning the written path."""
    target = path or paths.settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return target


def default_settings() -> AppSettings:
    """Return a fresh settings object with documented defaults."""
    return AppSettings()
