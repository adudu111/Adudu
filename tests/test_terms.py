"""Tests for terms (CRUD, profile-scoped uniqueness, ordering, duplication)."""

from __future__ import annotations

import pytest

from cyberglossary.database.repositories import (
    DuplicateTermNameError,
    ProfileNotFoundError,
    TermNotFoundError,
)


def _profile(profile_service):
    return profile_service.create_profile("Cyber Security")


def test_create_and_get(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    assert term.term == "LDAP"
    assert term.full_name == "Lightweight Directory Access Protocol"
    assert glossary_service.get_term(term.id) == term


def test_create_defaults(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP")
    assert term.full_name == ""


def test_create_rejects_empty_name(glossary_service, profile_service):
    pid = _profile(profile_service).id
    with pytest.raises(ValueError):
        glossary_service.create_term(pid, "   ")


def test_create_in_missing_profile_raises(glossary_service):
    with pytest.raises(ProfileNotFoundError):
        glossary_service.create_term(999, "LDAP")


def test_duplicate_name_within_profile_raises(glossary_service, profile_service):
    pid = _profile(profile_service).id
    glossary_service.create_term(pid, "LDAP")
    with pytest.raises(DuplicateTermNameError):
        glossary_service.create_term(pid, "LDAP")


def test_duplicate_name_is_case_insensitive(glossary_service, profile_service):
    pid = _profile(profile_service).id
    glossary_service.create_term(pid, "LDAP")
    with pytest.raises(DuplicateTermNameError):
        glossary_service.create_term(pid, "ldap")


def test_same_name_allowed_in_different_profiles(glossary_service, profile_service):
    pid_a = _profile(profile_service).id
    pid_b = profile_service.create_profile("Accounting").id
    glossary_service.create_term(pid_a, "SPN", "Service Principal Name")
    other = glossary_service.create_term(pid_b, "SPN", "Some Other Meaning")
    assert other.profile_id == pid_b


def test_list_terms_in_creation_order(glossary_service, profile_service):
    pid = _profile(profile_service).id
    a = glossary_service.create_term(pid, "LDAP")
    b = glossary_service.create_term(pid, "Kerberos")
    c = glossary_service.create_term(pid, "GPO")
    assert [t.term for t in glossary_service.list_terms(pid)] == ["LDAP", "Kerberos", "GPO"]
    assert [t.id for t in glossary_service.list_terms(pid)] == [a.id, b.id, c.id]


def test_list_terms_is_profile_scoped(glossary_service, profile_service):
    pid_a = _profile(profile_service).id
    pid_b = profile_service.create_profile("Accounting").id
    glossary_service.create_term(pid_a, "LDAP")
    assert glossary_service.list_terms(pid_b) == []


def test_rename_term(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP")
    updated = glossary_service.rename_term(term.id, "LDAPS")
    assert updated.term == "LDAPS"
    assert updated.id == term.id


def test_rename_duplicate_raises(glossary_service, profile_service):
    pid = _profile(profile_service).id
    glossary_service.create_term(pid, "LDAP")
    other = glossary_service.create_term(pid, "Kerberos")
    with pytest.raises(DuplicateTermNameError):
        glossary_service.rename_term(other.id, "ldap")


def test_rename_missing_raises(glossary_service):
    with pytest.raises(TermNotFoundError):
        glossary_service.rename_term(999, "X")


def test_set_full_name(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP")
    updated = glossary_service.set_full_name(term.id, "Lightweight Directory Access Protocol")
    assert updated.full_name == "Lightweight Directory Access Protocol"


def test_delete_term(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.delete_term(term.id)
    assert glossary_service.get_term(term.id) is None


def test_delete_missing_raises(glossary_service):
    with pytest.raises(TermNotFoundError):
        glossary_service.delete_term(12345)


def test_reorder_terms(glossary_service, profile_service):
    pid = _profile(profile_service).id
    a = glossary_service.create_term(pid, "A")
    b = glossary_service.create_term(pid, "B")
    c = glossary_service.create_term(pid, "C")
    glossary_service.reorder_terms(pid, [c.id, a.id, b.id])
    assert [t.term for t in glossary_service.list_terms(pid)] == ["C", "A", "B"]


def test_duplicate_copies_sections_and_aliases(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.add_section(term.id, "Definition", "A directory protocol")
    glossary_service.add_section(term.id, "Ports", "389")
    glossary_service.add_alias(term.id, "LDPA")

    copy = glossary_service.duplicate_term(term.id)

    assert copy.id != term.id
    assert copy.term == "LDAP (copy)"
    assert copy.full_name == "Lightweight Directory Access Protocol"
    assert [s.title for s in glossary_service.list_sections(copy.id)] == ["Definition", "Ports"]
    assert [s.content for s in glossary_service.list_sections(copy.id)] == [
        "A directory protocol",
        "389",
    ]
    assert [a.alias for a in glossary_service.list_aliases(copy.id)] == ["LDPA"]


def test_duplicate_generates_unique_copy_name(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP")
    first = glossary_service.duplicate_term(term.id)
    second = glossary_service.duplicate_term(term.id)
    assert first.term == "LDAP (copy)"
    assert second.term == "LDAP (copy 2)"


def test_duplicate_with_explicit_name(glossary_service, profile_service):
    pid = _profile(profile_service).id
    term = glossary_service.create_term(pid, "LDAP")
    copy = glossary_service.duplicate_term(term.id, new_term="LDAP v2")
    assert copy.term == "LDAP v2"


def test_duplicate_missing_raises(glossary_service):
    with pytest.raises(TermNotFoundError):
        glossary_service.duplicate_term(999)
