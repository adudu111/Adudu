"""Tests for dynamic sections (CRUD, ordering, and full dynamism)."""

from __future__ import annotations

import pytest

from cyberglossary.database.repositories import SectionNotFoundError, TermNotFoundError


def _term(glossary_service, profile_service):
    pid = profile_service.create_profile("Cyber Security").id
    return glossary_service.create_term(pid, "LDAP")


def test_term_starts_with_zero_sections(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    assert glossary_service.list_sections(term.id) == []


def test_add_and_get_section(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    section = glossary_service.add_section(term.id, "Definition", "A directory protocol")
    assert section.title == "Definition"
    assert section.content == "A directory protocol"
    assert [s.id for s in glossary_service.list_sections(term.id)] == [section.id]


def test_sections_are_fully_dynamic_titles(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    for title in ("Ports", "AS-REQ", "AS-REP", "TGT", "My Notes", "🔒 Detection"):
        glossary_service.add_section(term.id, title)
    assert [s.title for s in glossary_service.list_sections(term.id)] == [
        "Ports",
        "AS-REQ",
        "AS-REP",
        "TGT",
        "My Notes",
        "🔒 Detection",
    ]


def test_sections_are_per_term(glossary_service, profile_service):
    pid = profile_service.create_profile("Cyber Security").id
    ldap = glossary_service.create_term(pid, "LDAP")
    kerberos = glossary_service.create_term(pid, "Kerberos")

    glossary_service.add_section(ldap.id, "Ports")
    glossary_service.add_section(kerberos.id, "AS-REQ")

    assert [s.title for s in glossary_service.list_sections(ldap.id)] == ["Ports"]
    assert [s.title for s in glossary_service.list_sections(kerberos.id)] == ["AS-REQ"]


def test_add_section_preserves_order(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    glossary_service.add_section(term.id, "Definition")
    glossary_service.add_section(term.id, "Ports")
    glossary_service.add_section(term.id, "My Notes")
    assert [s.title for s in glossary_service.list_sections(term.id)] == [
        "Definition",
        "Ports",
        "My Notes",
    ]


def test_rename_section(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    section = glossary_service.add_section(term.id, "Definition")
    updated = glossary_service.rename_section(section.id, "What it is")
    assert updated.title == "What it is"


def test_rename_section_rejects_empty(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    section = glossary_service.add_section(term.id, "Definition")
    with pytest.raises(ValueError):
        glossary_service.rename_section(section.id, "   ")


def test_set_section_content(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    section = glossary_service.add_section(term.id, "Definition")
    updated = glossary_service.set_section_content(section.id, "Updated text")
    assert updated.content == "Updated text"


def test_reorder_sections(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    a = glossary_service.add_section(term.id, "A")
    b = glossary_service.add_section(term.id, "B")
    c = glossary_service.add_section(term.id, "C")

    glossary_service.reorder_sections(term.id, [c.id, a.id, b.id])
    assert [s.title for s in glossary_service.list_sections(term.id)] == ["C", "A", "B"]


def test_delete_section(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    section = glossary_service.add_section(term.id, "Definition")
    glossary_service.delete_section(section.id)
    assert glossary_service.list_sections(term.id) == []


def test_delete_missing_section_raises(glossary_service):
    with pytest.raises(SectionNotFoundError):
        glossary_service.delete_section(999)


def test_add_section_to_missing_term_raises(glossary_service):
    with pytest.raises(TermNotFoundError):
        glossary_service.add_section(999, "Definition")


def test_add_section_rejects_empty_title(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    with pytest.raises(ValueError):
        glossary_service.add_section(term.id, "   ")


def test_deleting_term_cascades_sections(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    glossary_service.add_section(term.id, "Definition")
    glossary_service.delete_term(term.id)
    assert glossary_service.list_sections(term.id) == []
