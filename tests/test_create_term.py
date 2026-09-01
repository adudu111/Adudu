"""Tests for the standalone New-Term creation window (createTerm + addSection flow).

Covers: create-term init (prefilled name + categories), the create/addSection flow via
bridge callbacks, and the window's drag/resize/close no-ops.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge
from cyberglossary.ui.web.create_term_window import CreateTermWindow


def _web_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"


def _make_bridge(profile_service, glossary_service, search_service, conn):
    calls = {"move": [], "resize": [], "close": []}
    bridge = Bridge(
        profile_service,
        glossary_service,
        search_service,
        LookupService(lambda: None, profile_service, glossary_service, search_service),
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=lambda d: None,
        on_file_action=lambda k: None,
        on_change_hotkey=lambda: None,
        on_capture_changed=lambda o: None,
        on_exit=lambda: None,
        get_hotkey_text=lambda: "Ctrl+Shift+D",
        on_request_create_term=lambda n: None,
        on_create_term_move=lambda: calls["move"].append(True),
        on_create_term_resize=lambda e: calls["resize"].append(e),
        on_create_term_close=lambda: calls["close"].append(True),
    )
    return bridge, calls


def test_create_term_init_prefills_name_and_categories(
    profile_service, glossary_service, search_service, conn
):
    import json

    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_category(pid, "cmd")
    glossary_service.create_category(pid, "net")
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    bridge.setCreateTermName("ldapsearch")
    data = json.loads(bridge.getCreateTermInit())
    assert data["name"] == "ldapsearch"
    assert data["categories"] == ["cmd", "net"]


def test_create_term_window_move_resize_close_callbacks(
    profile_service, glossary_service, search_service, conn
):
    bridge, calls = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.createTermMove()
    bridge.createTermResize("se")
    bridge.createTermClose()
    assert calls["move"] == [True]
    assert calls["resize"] == ["se"]
    assert calls["close"] == [True]


def test_create_term_window_no_raise(qapp, profile_service, glossary_service, search_service, conn):
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    w = CreateTermWindow(bridge, _web_dir())
    try:
        w.show_create_term()
        w.start_move()
        for edge in ("n", "s", "e", "w", "ne", "nw", "se", "sw", "bogus"):
            w.start_resize(edge)
        w.close_create_term()
        assert not w.isVisible()
    finally:
        w.deleteLater()
        qapp.processEvents()


def test_create_term_via_bridge_persists(profile_service, glossary_service, search_service, conn):
    import json

    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_category(pid, "cmd")
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    term = json.loads(bridge.createTerm("klist", "List Kerberos tickets", "cmd"))
    assert term["name"] == "klist"
    assert term["category"] == "cmd"

    sec = json.loads(bridge.addSection(term["id"], "Purpose", "Show cached tickets"))
    assert sec["content"] == "Show cached tickets"

    # Empty-name create is rejected.
    assert bridge.createTerm("   ", "", "") == "null"
