"""Standalone lookup popup queueing for the global hotkey path."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge
from cyberglossary.ui.web.lookup_popup import LookupPopupWindow


def _web_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"


def _bridge(profile_service, glossary_service, search_service, conn, **kwargs):
    return Bridge(
        profile_service, glossary_service, search_service,
        LookupService(lambda: None, profile_service, glossary_service, search_service),
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=lambda d: None, on_file_action=lambda k: None,
        on_change_hotkey=lambda: None, on_capture_changed=lambda o: None,
        on_exit=lambda: None, get_hotkey_text=lambda: "x",
        **kwargs,
    )


def test_lookup_result_queued_until_popup_ready(
    qapp, profile_service, glossary_service, search_service, conn
):
    bridge = _bridge(profile_service, glossary_service, search_service, conn)

    received = []
    bridge.lookupResult.connect(received.append)

    popup = LookupPopupWindow(bridge, _web_dir())

    # Before the popup page signals readiness, results are queued, not emitted.
    popup.show_result('{"found": true, "term": "LDAP"}')
    assert received == []

    # Once ready, the queued result is flushed.
    popup.on_bridge_ready()
    assert received == ['{"found": true, "term": "LDAP"}']

    # After ready, results are emitted immediately.
    popup.show_result('{"found": false, "query": "x"}')
    assert received == ['{"found": true, "term": "LDAP"}', '{"found": false, "query": "x"}']

    # Closing the popup must not raise and must not emit.
    popup.close_popup()
    assert len(received) == 2

    popup.deleteLater()
    qapp.processEvents()


def test_popup_close_and_open_callbacks(
    qapp, profile_service, glossary_service, search_service, conn
):
    closed = []
    opened = []
    bridge = _bridge(
        profile_service, glossary_service, search_service, conn,
        on_close_popup=lambda: closed.append(True),
        on_open_term=lambda tid, edit: opened.append((tid, edit)),
    )

    bridge.closePopup()
    assert closed == [True]

    bridge.openTerm(7, True)
    assert opened == [(7, True)]


def test_frontend_ready_slot_invokes_callback(qapp, profile_service, glossary_service, search_service, conn):
    ready_calls = []
    bridge = _bridge(
        profile_service, glossary_service, search_service, conn,
        on_ready=lambda: ready_calls.append(True),
    )
    bridge.frontendReady()
    assert ready_calls == [True]


def test_popup_move_and_resize_callbacks(qapp, profile_service, glossary_service, search_service, conn):
    moves = []
    resizes = []
    bridge = _bridge(
        profile_service, glossary_service, search_service, conn,
        on_start_move=lambda: moves.append(True),
        on_start_resize=lambda edge: resizes.append(edge),
    )

    bridge.startMove()
    assert moves == [True]

    bridge.startResize("se")
    bridge.startResize("nw")
    assert resizes == ["se", "nw"]


def test_popup_start_move_resize_no_raise(qapp, profile_service, glossary_service, search_service, conn):
    bridge = _bridge(profile_service, glossary_service, search_service, conn)
    popup = LookupPopupWindow(bridge, _web_dir())
    popup.show_result('{"found": true, "term": "LDAP"}')

    # Native system move/resize must not raise (no-op when no native handle).
    popup.start_move()
    popup.start_resize("se")
    popup.start_resize("bogus")

    popup.deleteLater()
    qapp.processEvents()


def test_popup_keeps_position_after_first_show(
    qapp, profile_service, glossary_service, search_service, conn
):
    bridge = _bridge(profile_service, glossary_service, search_service, conn)
    popup = LookupPopupWindow(bridge, _web_dir())
    popup.show_result('{"found": true, "term": "LDAP"}')
    popup.on_bridge_ready()

    x, y = popup.x(), popup.y()
    w, h = popup.width(), popup.height()

    # A second lookup while open must not reset size/position.
    popup.show_result('{"found": true, "term": "Kerberos"}')
    assert (popup.x(), popup.y(), popup.width(), popup.height()) == (x, y, w, h)

    popup.deleteLater()
    qapp.processEvents()
