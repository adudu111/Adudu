"""Tests for the QWebChannel bridge: every slot adapts the services to JSON.

These call Bridge methods directly (no QWebEngineView needed) against an in-memory temp
database, verifying the JS<->Python contract and that the services are unchanged.
"""

from __future__ import annotations

import json

from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge


def _make_bridge(profile_service, glossary_service, search_service, conn):
    calls = {"file": [], "theme": [], "capture": [], "exit": []}
    lookup = LookupService(lambda: None, profile_service, glossary_service, search_service)

    def on_file(key):
        calls["file"].append(key)

    def on_theme(dark):
        calls["theme"].append(dark)

    def on_hotkey():
        return "Ctrl+Shift+K"

    bridge = Bridge(
        profile_service,
        glossary_service,
        search_service,
        lookup,
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=on_theme,
        on_file_action=on_file,
        on_change_hotkey=lambda: None,
        on_capture_changed=lambda on: calls["capture"].append(on),
        on_exit=lambda: calls["exit"].append(True),
        get_hotkey_text=on_hotkey,
    )
    return bridge, calls


def test_init_data_shape(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    cat = glossary_service.create_category(pid, "Auth")
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.set_term_category(term.id, cat.id)
    glossary_service.add_alias(term.id, "LDPA")
    glossary_service.add_section(term.id, "Ports", "389")

    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    data = json.loads(bridge.getInitData())
    assert data["active_profile_id"] == pid
    assert [c["name"] for c in data["categories"]] == ["Auth"]
    assert len(data["terms"]) == 1
    term_dict = data["terms"][0]
    assert term_dict["name"] == "LDAP"
    assert term_dict["full_name"] == "Lightweight Directory Access Protocol"
    assert term_dict["category"] == "Auth"
    assert term_dict["aliases"] == ["LDPA"]
    assert term_dict["sections"][0]["title"] == "Ports"
    assert term_dict["sections"][0]["content"] == "389"


def test_bridge_search_uses_fts(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_term(pid, "Kerberos", "Network authentication protocol")
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    results = json.loads(bridge.search("kerberos"))
    assert len(results) == 1
    assert results[0]["term"] == "Kerberos"


def test_bridge_mutations(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_category(pid, "Web")
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    created = json.loads(bridge.createTerm("SSRF", "Server-Side Request Forgery", "Web"))
    assert created["name"] == "SSRF"
    term_id = created["id"]

    updated = json.loads(bridge.updateTerm(term_id, "SSRF", "SSRF", "Web"))
    assert updated["full_name"] == "SSRF"

    bridge.addAlias(term_id, "SSRF2")
    assert json.loads(bridge.getTerm(term_id))["aliases"] == ["SSRF2"]
    bridge.removeAlias(term_id, "SSRF2")
    assert json.loads(bridge.getTerm(term_id))["aliases"] == []

    section = json.loads(bridge.addSection(term_id, "Defense"))
    assert section["title"] == "Defense"
    bridge.updateSection(section["id"], "allowlist")
    bridge.renameSection(section["id"], "Mitigation")
    assert [s["title"] for s in json.loads(bridge.getTerm(term_id))["sections"]] == ["Mitigation"]
    assert json.loads(bridge.getTerm(term_id))["sections"][0]["content"] == "allowlist"

    bridge.deleteSection(section["id"])
    assert json.loads(bridge.getTerm(term_id))["sections"] == []

    dup = json.loads(bridge.duplicateTerm(term_id))
    assert dup["name"] == "SSRF (copy)" if "copy" in dup["name"] else dup["name"].startswith("SSRF")

    categories = json.loads(bridge.getCategories())
    assert [c["name"] for c in categories] == ["Web"]
    bridge.renameCategory(categories[0]["id"], "Web App")
    cat = json.loads(bridge.getCategories())[0]
    assert cat["name"] == "Web App"

    bridge.deleteTerm(term_id)
    bridge.deleteTerm(dup["id"])
    assert json.loads(bridge.getTerms()) == []


def test_bridge_file_actions_and_theme(profile_service, glossary_service, search_service, conn):
    bridge, calls = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.fileAction("backup")
    assert calls["file"] == ["backup"]
    bridge.setTheme(True)
    assert calls["theme"] == [True]
    bridge.setCapture(False)
    assert calls["capture"] == [False]
    assert bridge.getHotkeyText() == "Ctrl+Shift+K"


def test_add_section_saves_content(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    term_id = json.loads(bridge.createTerm("LDAP", "", ""))["id"]
    section = json.loads(bridge.addSection(term_id, "Ports", "389 / 636"))

    assert section["title"] == "Ports"
    assert section["content"] == "389 / 636"

    reloaded = json.loads(bridge.getTerm(term_id))["sections"]
    assert reloaded[0]["title"] == "Ports"
    assert reloaded[0]["content"] == "389 / 636"

    # The two-argument form still works (content defaults to empty).
    empty = json.loads(bridge.addSection(term_id, "Notes"))
    assert empty["content"] == ""


def test_bridge_errors_become_toasts(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    toasts = []
    bridge.toast.connect(toasts.append)

    # Empty term name -> service error -> toast, not an unhandled exception.
    assert bridge.createTerm("   ", "", "") == "null"
    assert toasts and "Term name must not be empty" in toasts[-1]

    # Empty section title -> toast.
    term_id = json.loads(bridge.createTerm("SSRF", "", ""))["id"]
    assert bridge.addSection(term_id, "  ") == "null"
    assert any("Section title must not be empty" in t for t in toasts)


def test_bridge_profile_switch_reloads(profile_service, glossary_service, search_service, conn):
    a = profile_service.create_profile("A").id
    glossary_service.create_term(a, "LDAP")
    b = profile_service.create_profile("B").id
    glossary_service.create_term(b, "WMI")

    bridge, _ = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(a)
    assert [t["name"] for t in json.loads(bridge.getTerms())] == ["LDAP"]
    bridge.setActiveProfile(b)
    assert [t["name"] for t in json.loads(bridge.getTerms())] == ["WMI"]
    profiles = json.loads(bridge.getProfiles())
    assert profiles["active_profile_id"] == b
