"""Tests for normalization and the lookup resolution pipeline."""

from __future__ import annotations

from cyberglossary.services.lookup_service import (
    LookupResult,
    LookupService,
    normalize_selected_text,
)

# --- normalization ---------------------------------------------------------


def test_normalize_empty():
    assert normalize_selected_text("") == ""
    assert normalize_selected_text("   ") == ""
    assert normalize_selected_text("\n\t") == ""


def test_normalize_whitespace_and_newlines():
    assert normalize_selected_text("  LDAP  ") == "LDAP"
    assert normalize_selected_text("LDAP\n") == "LDAP"
    assert normalize_selected_text("LDAP\nLightweight") == "LDAP Lightweight"


def test_normalize_surrounding_quotes():
    assert normalize_selected_text('"LDAP"') == "LDAP"
    assert normalize_selected_text("'LDAP'") == "LDAP"


def test_normalize_trailing_punctuation():
    assert normalize_selected_text("LDAP,") == "LDAP"
    assert normalize_selected_text("LDAP.") == "LDAP"
    assert normalize_selected_text("LDAP:") == "LDAP"


def test_normalize_parenthesized_full_name():
    assert normalize_selected_text("LDAP (Lightweight Directory Access Protocol)") == "LDAP"


def test_normalize_long_text():
    assert normalize_selected_text("   LDAP    ") == "LDAP"


# --- lookup ----------------------------------------------------------------


def test_lookup_exact_term(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    result = lookup_service.lookup("LDAP")
    assert result.found is True
    assert result.term_id == term.id
    assert result.term == "LDAP"


def test_lookup_exact_term_case_insensitive(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    assert lookup_service.lookup("ldap").term_id == term.id


def test_lookup_exact_alias(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_alias(term.id, "Lightweight Directory Access Protocol")
    result = lookup_service.lookup("Lightweight Directory Access Protocol")
    assert result.found is True
    assert result.term_id == term.id
    assert result.term == "LDAP"


def test_lookup_alias_case_insensitive(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_alias(term.id, "LDPA")
    assert lookup_service.lookup("ldpa").term_id == term.id


def test_lookup_fts_fallback(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "Kerberos")
    glossary_service.add_section(term.id, "Attack", "golden ticket forgery")
    result = lookup_service.lookup("golden ticket")
    assert result.found is True
    assert result.term_id == term.id


def test_lookup_not_found(lookup_service, profile_service, glossary_service):
    profile_service.create_profile("Cyber Security")
    result = lookup_service.lookup("nonexistent")
    assert result.found is False
    assert result.query == "nonexistent"


def test_lookup_active_profile_isolation(lookup_service, profile_service, glossary_service):
    cyber = profile_service.create_profile("Cyber Security")
    accounting = profile_service.create_profile("Accounting")
    glossary_service.create_term(accounting.id, "SPN", "Some Other Meaning")

    # First-created profile stays active; SPN lives in Accounting only.
    assert profile_service.get_active_profile_id() == cyber.id
    assert lookup_service.lookup("SPN").found is False

    profile_service.set_active_profile(accounting.id)
    assert lookup_service.lookup("SPN").found is True


def test_lookup_exact_match_priority_over_fts(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    ldap = glossary_service.create_term(pid, "LDAP")
    glossary_service.create_term(pid, "LDAP Injection")
    result = lookup_service.lookup("LDAP")
    assert result.term_id == ldap.id
    assert result.term == "LDAP"


def test_lookup_no_active_profile(lookup_service):
    result = lookup_service.lookup("LDAP")
    assert result.found is False


def test_lookup_result_populates_metadata(lookup_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.add_section(term.id, "Ports", "389")
    glossary_service.add_section(term.id, "Definition", "A directory protocol")
    category = glossary_service.create_category(pid, "Active Directory")
    glossary_service.set_term_category(term.id, category.id)
    glossary_service.set_term_tags(term.id, ["Protocol"])

    result = lookup_service.lookup("LDAP")
    assert result.full_name == "Lightweight Directory Access Protocol"
    assert result.category == "Active Directory"
    assert result.tags == ["Protocol"]
    assert [s.title for s in result.sections] == ["Ports", "Definition"]
    assert result.profile_name == "Cyber Security"


def test_lookup_run_with_capture(profile_service, glossary_service, search_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    service = LookupService(
        lambda: '"LDAP"', profile_service, glossary_service, search_service
    )
    result = service.run()
    assert result.found is True
    assert result.term_id == term.id


def test_lookup_run_empty_capture(profile_service, glossary_service, search_service):
    service = LookupService(lambda: None, profile_service, glossary_service, search_service)
    assert service.run().found is False


def test_not_found_result_shape():
    result = LookupResult.not_found("LDAP")
    assert result.found is False
    assert result.query == "LDAP"
    assert result.sections == []
    assert result.tags == []
