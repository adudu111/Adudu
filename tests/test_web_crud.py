"""Phase 3: real term CRUD through the bridge → services → repository → SQLite."""

from __future__ import annotations

import json

from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge


def _make_bridge(profile_service, glossary_service, search_service, conn):
    lookup = LookupService(lambda: None, profile_service, glossary_service, search_service)
    return Bridge(
        profile_service,
        glossary_service,
        search_service,
        lookup,
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=lambda d: None,
        on_file_action=lambda k: None,
        on_change_hotkey=lambda: None,
        on_capture_changed=lambda o: None,
        on_exit=lambda: None,
        get_hotkey_text=lambda: "Ctrl+Shift+K",
    )


def _names(glossary_service, pid):
    return [t.term for t in glossary_service.list_terms(pid)]


def test_term_crud_full_cycle(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    # CREATE
    created = json.loads(bridge.createTerm("SSRF", "Server-Side Request Forgery", ""))
    assert created["name"] == "SSRF"
    term_id = created["id"]
    assert _names(glossary_service, pid) == ["SSRF"]

    # GET
    fetched = json.loads(bridge.getTerm(term_id))
    assert fetched["name"] == "SSRF"
    assert fetched["full_name"] == "Server-Side Request Forgery"

    # UPDATE (rename + full name)
    updated = json.loads(bridge.updateTerm(term_id, "SSRF", "SSRF full", ""))
    assert updated["name"] == "SSRF"
    assert updated["full_name"] == "SSRF full"
    assert glossary_service.get_term(term_id).term == "SSRF"
    assert glossary_service.get_term(term_id).full_name == "SSRF full"

    # DUPLICATE
    dup = json.loads(bridge.duplicateTerm(term_id))
    assert dup["id"] != term_id
    assert dup["name"].startswith("SSRF")
    assert len(_names(glossary_service, pid)) == 2

    # MULTI DELETE
    assert bridge.deleteTerm(term_id) is True
    assert bridge.deleteTerm(dup["id"]) is True
    assert _names(glossary_service, pid) == []


def test_term_delete_persists(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    t = json.loads(bridge.createTerm("WMI", "", ""))
    assert bridge.deleteTerm(t["id"]) is True
    assert glossary_service.get_term(t["id"]) is None


def test_create_term_empty_name_errors_toast(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    toasts = []
    bridge.toast.connect(toasts.append)
    assert bridge.createTerm("   ", "", "") == "null"
    assert toasts and "Term name must not be empty" in toasts[-1]
