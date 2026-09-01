"""Tests for the global search launcher (Phase 2, additive).

Covers: launcher search (grouped, categories-first), recents/pins, copy, the second
global hotkey (and that the existing lookup hotkey is unchanged), and the launcher
window's minimize/restore, drag/resize, and close/reopen behavior.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from cyberglossary.config.settings import AppSettings
from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge
from cyberglossary.ui.web.launcher_window import LauncherWindow
from cyberglossary.windows.hotkey import (
    DEFAULT_HOTKEY,
    Hotkey,
    HotkeyService,
    format_hotkey,
)


def _web_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"


def _make_bridge(profile_service, glossary_service, search_service, conn, settings=None):
    calls = {"copy": [], "recent": [], "pin": [], "close": [], "minimize": [], "restore": []}
    lookup = LookupService(lambda: None, profile_service, glossary_service, search_service)
    bridge = Bridge(
        profile_service,
        glossary_service,
        search_service,
        lookup,
        BackupService(conn, ":memory:"),
        settings_store=settings,
        on_theme=lambda d: None,
        on_file_action=lambda k: None,
        on_change_hotkey=lambda: None,
        on_capture_changed=lambda o: None,
        on_exit=lambda: None,
        get_hotkey_text=lambda: "Ctrl+Shift+D",
        on_copy_text=lambda t: calls["copy"].append(t),
        on_launcher_recent=lambda i: calls["recent"].append(i),
        on_launcher_pin=lambda i: calls["pin"].append(i),
        on_launcher_close=lambda: calls["close"].append(True),
        on_launcher_minimize=lambda: calls["minimize"].append(True),
        on_launcher_restore=lambda: calls["restore"].append(True),
    )
    return bridge, calls


def _seed(profile_service, glossary_service):
    pid = profile_service.create_profile("CRTO").id
    cat_ticket = glossary_service.create_category(pid, "TICKET SEARCHING")
    cat_cmd = glossary_service.create_category(pid, "CMD")

    klist = glossary_service.create_term(pid, "klist", "View cached Kerberos tickets")
    glossary_service.set_term_category(klist.id, cat_ticket.id)
    glossary_service.add_section(klist.id, "Purpose", "List the cached Kerberos tickets")

    ipconfig = glossary_service.create_term(pid, "ipconfig", "Show network configuration")
    glossary_service.set_term_category(ipconfig.id, cat_cmd.id)
    glossary_service.add_section(ipconfig.id, "Purpose", "Display TCP/IP network config")

    return pid, klist.id, ipconfig.id


# --- search / grouping -----------------------------------------------------


def test_launcher_search_groups_by_category(profile_service, glossary_service, search_service, conn):
    pid, _klist_id, _ = _seed(profile_service, glossary_service)
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    data = json.loads(bridge.launcherSearch("ticket"))
    assert data["count"] >= 1
    categories = [g["category"] for g in data["groups"]]
    assert categories[0] == "TICKET SEARCHING"  # matching category first
    terms = {t["term"] for g in data["groups"] for t in g["terms"]}
    assert "klist" in terms


def test_launcher_search_matches_term_name(profile_service, glossary_service, search_service, conn):
    pid, _klist_id, _ = _seed(profile_service, glossary_service)
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    data = json.loads(bridge.launcherSearch("klist"))
    terms = {t["term"] for g in data["groups"] for t in g["terms"]}
    assert "klist" in terms
    assert "TICKET SEARCHING" in [g["category"] for g in data["groups"]]


def test_launcher_search_uncategorized(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_term(pid, "whoami", "Show current user")
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    data = json.loads(bridge.launcherSearch("whoami"))
    assert "Uncategorized" in [g["category"] for g in data["groups"]]


# --- recents / pins --------------------------------------------------------


def test_launcher_init_returns_recent_and_pinned(profile_service, glossary_service, search_service, conn):
    pid, klist_id, ipconfig_id = _seed(profile_service, glossary_service)
    settings = AppSettings()
    settings.launcher_recent = [klist_id]
    settings.launcher_pinned = [ipconfig_id]
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn, settings)
    bridge.setActiveProfile(pid)

    data = json.loads(bridge.launcherInit())
    assert [t["name"] for t in data["recent"]] == ["klist"]
    assert [t["name"] for t in data["pinned"]] == ["ipconfig"]


def test_launcher_recent_and_pin_callbacks(profile_service, glossary_service, search_service, conn):
    bridge, calls = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.launcherAddRecent(5)
    bridge.launcherTogglePin(7)
    assert calls["recent"] == [5]
    assert calls["pin"] == [7]


# --- copy ------------------------------------------------------------------


def test_copy_text_routes_to_callback(profile_service, glossary_service, search_service, conn):
    bridge, calls = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.copyText("klist")
    assert calls["copy"] == ["klist"]


# --- window controls -------------------------------------------------------


def test_launcher_window_minimize_restore(qapp, profile_service, glossary_service, search_service, conn):
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    w = LauncherWindow(bridge, _web_dir())
    try:
        w.show_launcher()
        w.minimize()
        assert w._minimized is True
        assert w.height() == 48
        w.restore()
        assert w._minimized is False
        assert w.height() == 560
    finally:
        w.deleteLater()
        qapp.processEvents()


def test_launcher_window_start_move_resize_no_raise(qapp, profile_service, glossary_service, search_service, conn):
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    w = LauncherWindow(bridge, _web_dir())
    try:
        w.start_move()
        for edge in ("n", "s", "e", "w", "ne", "nw", "se", "sw", "bogus"):
            w.start_resize(edge)
    finally:
        w.deleteLater()
        qapp.processEvents()


def test_launcher_window_close_and_reopen(qapp, profile_service, glossary_service, search_service, conn):
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    w = LauncherWindow(bridge, _web_dir())
    w.show_launcher()
    assert w.isVisible()
    w.close_launcher()
    assert not w.isVisible()
    w.deleteLater()
    qapp.processEvents()

    # Recreate (simulating the hotkey lazily re-opening it after a close).
    w2 = LauncherWindow(bridge, _web_dir())
    try:
        w2.show_launcher()
        assert w2.isVisible()
    finally:
        w2.deleteLater()
        qapp.processEvents()


# --- two hotkeys coexist ---------------------------------------------------


class _Backend:
    def __init__(self):
        self.registered = []

    def register(self, hotkey):
        self.registered.append(hotkey)
        return True

    def unregister(self):
        return True


def test_two_hotkey_services_are_independent(monkeypatch):
    lookup_backend = _Backend()
    launcher_backend = _Backend()
    lookup = HotkeyService(0, DEFAULT_HOTKEY, hotkey_id=1)
    launcher = HotkeyService(0, Hotkey(6, 0x20), hotkey_id=2)
    monkeypatch.setattr(lookup, "_register_native", lookup_backend.register)
    monkeypatch.setattr(lookup, "_unregister_native", lookup_backend.unregister)
    monkeypatch.setattr(launcher, "_register_native", launcher_backend.register)
    monkeypatch.setattr(launcher, "_unregister_native", launcher_backend.unregister)

    assert lookup.register() is True
    assert launcher.register() is True
    assert lookup._id == 1
    assert launcher._id == 2
    assert lookup_backend.registered == [DEFAULT_HOTKEY]
    assert launcher_backend.registered == [Hotkey(6, 0x20)]

    # Changing one must not touch the other.
    launcher.change(Hotkey(2, 0x4B))  # Ctrl+K
    assert lookup.current_hotkey() == DEFAULT_HOTKEY
    assert launcher.current_hotkey() == Hotkey(2, 0x4B)


def test_existing_lookup_hotkey_unchanged():
    assert DEFAULT_HOTKEY == Hotkey(6, 0x44)  # Ctrl+Shift+D
    assert format_hotkey(DEFAULT_HOTKEY) == "Ctrl + Shift + D"
