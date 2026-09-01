"""Tests for alias management (user-controlled only)."""

from __future__ import annotations

import pytest

from cyberglossary.database.repositories import (
    AliasNotFoundError,
    DuplicateAliasError,
    TermNotFoundError,
)


def _term(glossary_service, profile_service):
    pid = profile_service.create_profile("Cyber Security").id
    return glossary_service.create_term(pid, "LDAP")


def test_add_and_list_alias(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    alias = glossary_service.add_alias(term.id, "Lightweight Directory Access Protocol")
    assert alias.alias == "Lightweight Directory Access Protocol"
    assert [a.alias for a in glossary_service.list_aliases(term.id)] == [
        "Lightweight Directory Access Protocol"
    ]


def test_add_multiple_aliases(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    glossary_service.add_alias(term.id, "LDPA")
    glossary_service.add_alias(term.id, "Lightweight Directory Access Protocol")
    assert {a.alias for a in glossary_service.list_aliases(term.id)} == {
        "LDPA",
        "Lightweight Directory Access Protocol",
    }


def test_duplicate_alias_raises(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    glossary_service.add_alias(term.id, "LDPA")
    with pytest.raises(DuplicateAliasError):
        glossary_service.add_alias(term.id, "LDPA")


def test_duplicate_alias_is_case_insensitive(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    glossary_service.add_alias(term.id, "LDPA")
    with pytest.raises(DuplicateAliasError):
        glossary_service.add_alias(term.id, "ldpa")


def test_same_alias_allowed_across_terms(glossary_service, profile_service):
    pid = profile_service.create_profile("Cyber Security").id
    ldap = glossary_service.create_term(pid, "LDAP")
    other = glossary_service.create_term(pid, "Active Directory")
    glossary_service.add_alias(ldap.id, "Directory")
    glossary_service.add_alias(other.id, "Directory")
    assert [a.alias for a in glossary_service.list_aliases(other.id)] == ["Directory"]


def test_delete_alias(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    alias = glossary_service.add_alias(term.id, "LDPA")
    glossary_service.delete_alias(alias.id)
    assert glossary_service.list_aliases(term.id) == []


def test_delete_missing_alias_raises(glossary_service):
    with pytest.raises(AliasNotFoundError):
        glossary_service.delete_alias(999)


def test_add_alias_to_missing_term_raises(glossary_service):
    with pytest.raises(TermNotFoundError):
        glossary_service.add_alias(999, "LDPA")


def test_add_alias_rejects_empty(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    with pytest.raises(ValueError):
        glossary_service.add_alias(term.id, "   ")


def test_deleting_term_cascades_aliases(glossary_service, profile_service):
    term = _term(glossary_service, profile_service)
    glossary_service.add_alias(term.id, "LDPA")
    glossary_service.delete_term(term.id)
    assert glossary_service.list_aliases(term.id) == []
