"""Tests for the search query builder and the FTS5 search service."""

from __future__ import annotations

from cyberglossary.services.search_service import SearchQueryBuilder

# --- query builder --------------------------------------------------------


def test_builder_simple_token():
    assert SearchQueryBuilder.build("ldap") == "ldap"


def test_builder_quoted_phrase():
    assert SearchQueryBuilder.build('"ldap injection"') == '"ldap injection"'


def test_builder_prefix():
    assert SearchQueryBuilder.build("kerb*") == "kerb*"


def test_builder_boolean_or():
    assert SearchQueryBuilder.build("ports OR 389") == "ports OR 389"


def test_builder_negation():
    assert SearchQueryBuilder.build("-tgt") == ""
    assert SearchQueryBuilder.negated_terms("-tgt") == ["tgt"]


def test_builder_negated_with_positive():
    assert SearchQueryBuilder.build("ldap -kerberos") == "ldap"
    assert SearchQueryBuilder.negated_terms("ldap -kerberos") == ["kerberos"]


def test_builder_empty_input():
    assert SearchQueryBuilder.build("") == ""


def test_builder_whitespace_only():
    assert SearchQueryBuilder.build("   \n\t ") == ""


def test_builder_strips_punctuation():
    assert SearchQueryBuilder.build("ldap,") == "ldap"
    assert SearchQueryBuilder.build("(ldap)") == "ldap"


def test_builder_parentheses_grouping():
    assert SearchQueryBuilder.build("(ports OR 389)") == "ports OR 389"


def test_builder_colon_is_sanitized():
    assert SearchQueryBuilder.build("term:ldap") == "termldap"


def test_builder_bare_asterisk_dropped():
    assert SearchQueryBuilder.build("*") == ""


def test_builder_unbalanced_quote_is_safe():
    assert SearchQueryBuilder.build('"unclosed') == '"unclosed"'


def test_builder_malformed_does_not_raise():
    for query in ('""', '---', ':::', ')(', '"a" OR OR OR', '  *  '):
        SearchQueryBuilder.build(query)  # must not raise


def test_builder_very_long_input_is_truncated():
    result = SearchQueryBuilder.build("x" * 5000)
    assert len(result) <= 1024


# --- search service -------------------------------------------------------


def _search_ids(search_service, query, profile_id=None):
    return {r.term_id for r in search_service.search(query, profile_id)}


def test_search_finds_term_by_name(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    assert _search_ids(search_service, "ldap", pid) == {term.id}


def test_search_finds_full_name(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    assert _search_ids(search_service, "lightweight", pid) == {term.id}


def test_search_finds_alias(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_alias(term.id, "LDPA")
    assert _search_ids(search_service, "ldpa", pid) == {term.id}


def test_search_finds_section_content(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_section(term.id, "Ports", "389 and 636")
    assert _search_ids(search_service, "636", pid) == {term.id}


def test_search_finds_tag(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.set_term_tags(term.id, ["Protocol", "Windows"])
    assert _search_ids(search_service, "protocol", pid) == {term.id}


def test_search_finds_category(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    category = glossary_service.create_category(pid, "Active Directory")
    glossary_service.set_term_category(term.id, category.id)
    assert _search_ids(search_service, "active", pid) == {term.id}


def test_search_prefix(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    kerberos = glossary_service.create_term(pid, "Kerberos")
    glossary_service.create_term(pid, "LDAP")
    assert _search_ids(search_service, "kerb*", pid) == {kerberos.id}


def test_search_phrase(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_section(term.id, "Definition", "directory access protocol")
    assert _search_ids(search_service, '"directory access"', pid) == {term.id}


def test_search_boolean_or(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    ldap = glossary_service.create_term(pid, "LDAP")
    kerberos = glossary_service.create_term(pid, "Kerberos")
    assert _search_ids(search_service, "ldap OR kerberos", pid) == {ldap.id, kerberos.id}


def test_search_negation(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    ldap = glossary_service.create_term(pid, "LDAP")
    glossary_service.create_term(pid, "Kerberos")
    assert _search_ids(search_service, "-kerberos", pid) == {ldap.id}


def test_search_profile_isolation(search_service, profile_service, glossary_service):
    pid_a = profile_service.create_profile("Cyber Security").id
    pid_b = profile_service.create_profile("Accounting").id
    a = glossary_service.create_term(pid_a, "SPN", "Service Principal Name")
    b = glossary_service.create_term(pid_b, "SPN", "Some Other Meaning")

    assert _search_ids(search_service, "spn", pid_a) == {a.id}
    assert _search_ids(search_service, "spn", pid_b) == {b.id}
    assert _search_ids(search_service, "spn") == {a.id, b.id}


def test_search_result_includes_metadata(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.add_section(term.id, "Definition", "A directory access protocol.")
    category = glossary_service.create_category(pid, "Active Directory")
    glossary_service.set_term_category(term.id, category.id)

    results = search_service.search("directory", pid)
    assert results
    result = results[0]
    assert result.term == "LDAP"
    assert result.full_name == "Lightweight Directory Access Protocol"
    assert result.profile_name == "Cyber Security"
    assert result.category == "Active Directory"
    assert result.snippet is not None


def test_search_no_results(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    assert search_service.search("nonexistent", pid) == []


def test_search_empty_query_returns_empty(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    assert search_service.search("", pid) == []
    assert search_service.search("   ", pid) == []


def test_search_malformed_input_fails_safely(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    for query in ('"a" OR OR OR', ":::(", "NOT NOT", "-", "* * *"):
        assert search_service.search(query, pid) == []
