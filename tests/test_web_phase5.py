"""Phase 5: real FTS5 search through the bridge."""

from __future__ import annotations

import json

from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge


def _make_bridge(profile_service, glossary_service, search_service, conn):
    lookup = LookupService(lambda: None, profile_service, glossary_service, search_service)
    return Bridge(
        profile_service, glossary_service, search_service, lookup,
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=lambda d: None, on_file_action=lambda k: None,
        on_change_hotkey=lambda: None, on_capture_changed=lambda o: None,
        on_exit=lambda: None, get_hotkey_text=lambda: "Ctrl+Shift+K",
    )


def _terms(bridge, query):
    return [r["term"] for r in json.loads(bridge.searchTerms(query))]


def test_search_fields_and_scoping(profile_service, glossary_service, search_service, conn):
    a = profile_service.create_profile("A").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)

    term = glossary_service.create_term(a, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.add_alias(term.id, "LDPA")
    glossary_service.add_section(term.id, "Ports", "389 ldap")
    cat = glossary_service.create_category(a, "Auth")
    glossary_service.set_term_category(term.id, cat.id)

    bridge.setActiveProfile(a)

    # exact term
    assert _terms(bridge, "ldap") == ["LDAP"]
    # prefix
    assert _terms(bridge, "lda*") == ["LDAP"]
    # full name
    assert _terms(bridge, "lightweight") == ["LDAP"]
    # alias
    assert _terms(bridge, "ldpa") == ["LDAP"]
    # section content
    assert _terms(bridge, "389") == ["LDAP"]
    # category
    assert _terms(bridge, "auth") == ["LDAP"]
    # no results
    assert _terms(bridge, "zzzzzz") == []


def test_search_is_profile_scoped(profile_service, glossary_service, search_service, conn):
    a = profile_service.create_profile("A").id
    b = profile_service.create_profile("B").id
    glossary_service.create_term(a, "LDAP")
    glossary_service.create_term(b, "WMI")

    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(a)
    assert _terms(bridge, "ldap") == ["LDAP"]
    assert _terms(bridge, "wmi") == []

    bridge.setActiveProfile(b)
    assert _terms(bridge, "wmi") == ["WMI"]
    assert _terms(bridge, "ldap") == []
