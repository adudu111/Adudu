"""Phase 4: categories, aliases and dynamic sections through the bridge → SQLite."""

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


def test_categories_full_cycle(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    a = json.loads(bridge.createCategory("A"))
    b = json.loads(bridge.createCategory("B"))
    c = json.loads(bridge.createCategory("C"))
    assert [x["name"] for x in json.loads(bridge.getCategories())] == ["A", "B", "C"]

    bridge.renameCategory(b["id"], "B2")
    assert [x["name"] for x in json.loads(bridge.getCategories())] == ["A", "B2", "C"]

    # reorder: C, A, B2
    bridge.reorderCategories(json.dumps([c["id"], a["id"], b["id"]]))
    assert [x["name"] for x in json.loads(bridge.getCategories())] == ["C", "A", "B2"]

    # assign + clear category on a term; delete category keeps the term
    t = json.loads(bridge.createTerm("LDAP", "", ""))
    assert bridge.assignCategory(t["id"], "C") is True
    assert json.loads(bridge.getTerm(t["id"]))["category"] == "C"
    assert bridge.clearCategory(t["id"]) is True
    assert json.loads(bridge.getTerm(t["id"]))["category"] is None

    bridge.deleteCategory(c["id"])
    assert [x["name"] for x in json.loads(bridge.getCategories())] == ["A", "B2"]
    # term survives category deletion
    assert json.loads(bridge.getTerm(t["id"]))["name"] == "LDAP"


def test_aliases_full_cycle(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    t = json.loads(bridge.createTerm("Kerberos", "", ""))
    assert bridge.addAlias(t["id"], "KDC") is True
    assert bridge.addAlias(t["id"], "TGT") is True
    assert json.loads(bridge.getAliases(t["id"])) == ["KDC", "TGT"]
    assert bridge.removeAlias(t["id"], "KDC") is True
    assert json.loads(bridge.getAliases(t["id"])) == ["TGT"]


def test_sections_full_cycle(profile_service, glossary_service, search_service, conn):
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    t = json.loads(bridge.createTerm("SSRF", "", ""))
    s1 = json.loads(bridge.addSection(t["id"], "A"))
    s2 = json.loads(bridge.addSection(t["id"], "B"))
    s3 = json.loads(bridge.addSection(t["id"], "C"))
    assert [s["title"] for s in json.loads(bridge.getSections(t["id"]))] == ["A", "B", "C"]

    # edit content
    assert bridge.updateSection(s3["id"], "content for C") is True
    assert bridge.renameSection(s3["id"], "C2") is True
    sections = json.loads(bridge.getSections(t["id"]))
    assert [s["title"] for s in sections] == ["A", "B", "C2"]
    assert sections[2]["content"] == "content for C"

    # reorder: move C2 up → A, C2, B
    ordered = [s1["id"], s3["id"], s2["id"]]
    assert bridge.reorderSections(t["id"], json.dumps(ordered)) is True
    assert [s["title"] for s in json.loads(bridge.getSections(t["id"]))] == ["A", "C2", "B"]

    # delete
    assert bridge.deleteSection(s1["id"]) is True
    assert [s["title"] for s in json.loads(bridge.getSections(t["id"]))] == ["C2", "B"]


def test_section_order_persists_across_reopen(profile_service, glossary_service, search_service, conn):
    # Order is stored in SQLite via sort_order; a fresh service view must match.
    pid = profile_service.create_profile("CRTO").id
    bridge = _make_bridge(profile_service, glossary_service, search_service, conn)
    bridge.setActiveProfile(pid)

    t = json.loads(bridge.createTerm("T", "", ""))
    a = json.loads(bridge.addSection(t["id"], "A"))
    b = json.loads(bridge.addSection(t["id"], "B"))
    c = json.loads(bridge.addSection(t["id"], "C"))
    bridge.reorderSections(t["id"], json.dumps([c["id"], a["id"], b["id"]]))

    # A fresh read through the service (simulating restart) reflects the persisted order.
    assert [s.title for s in glossary_service.list_sections(t["id"])] == ["C", "A", "B"]
