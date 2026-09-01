"""Phase 6: lookup through the bridge (LookupService), and the lookupResult signal."""

from __future__ import annotations

import json

from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge, _lookup_dict


def _make_bridge(profile_service, glossary_service, search_service, conn, capture=lambda: None):
    lookup = LookupService(capture, profile_service, glossary_service, search_service)
    return lookup, Bridge(
        profile_service, glossary_service, search_service, lookup,
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=lambda d: None, on_file_action=lambda k: None,
        on_change_hotkey=lambda: None, on_capture_changed=lambda o: None,
        on_exit=lambda: None, get_hotkey_text=lambda: "Ctrl+Shift+K",
    )


def test_bridge_lookup_returns_real_term(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.add_alias(term.id, "LDPA")
    glossary_service.add_section(term.id, "Ports", "389")

    _lookup, bridge = _make_bridge(profile_service, glossary_service, search_service, conn, lambda: None)
    bridge.setActiveProfile(pid)

    data = json.loads(bridge.lookup("LDAP"))
    assert data["found"] is True
    assert data["term"] == "LDAP"
    assert data["full_name"] == "Lightweight Directory Access Protocol"
    assert data["sections"][0]["title"] == "Ports"

    not_found = json.loads(bridge.lookup("DoesNotExist"))
    assert not_found["found"] is False


def test_lookup_result_signal_emits(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_term(pid, "LDAP")

    lookup, bridge = _make_bridge(profile_service, glossary_service, search_service, conn, lambda: "LDAP")
    bridge.setActiveProfile(pid)

    received = []
    bridge.lookupResult.connect(received.append)
    result = lookup.run()
    bridge.lookupResult.emit(json.dumps(_lookup_dict(result)))

    assert received
    assert json.loads(received[0])["term"] == "LDAP"
