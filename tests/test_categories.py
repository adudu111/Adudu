"""Tests for the completed category feature (service layer)."""

from __future__ import annotations


def test_category_crud(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "Active Directory")
    assert [c.name for c in glossary_service.list_categories(pid)] == ["Active Directory"]

    glossary_service.rename_category(category.id, "Directory Services")
    assert glossary_service.list_categories(pid)[0].name == "Directory Services"

    glossary_service.delete_category(category.id)
    assert glossary_service.list_categories(pid) == []


def test_category_reorder(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    a = glossary_service.create_category(pid, "A")
    b = glossary_service.create_category(pid, "B")
    c = glossary_service.create_category(pid, "C")

    glossary_service.reorder_categories(pid, [c.id, a.id, b.id])
    assert [x.name for x in glossary_service.list_categories(pid)] == ["C", "A", "B"]


def test_assign_change_clear_category(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    cat_a = glossary_service.create_category(pid, "Active Directory")
    cat_b = glossary_service.create_category(pid, "Networking")
    term = glossary_service.create_term(pid, "LDAP")

    glossary_service.set_term_category(term.id, cat_a.id)
    assert glossary_service.get_term_category(term.id).name == "Active Directory"

    glossary_service.set_term_category(term.id, cat_b.id)
    assert glossary_service.get_term_category(term.id).name == "Networking"

    glossary_service.set_term_category(term.id, None)
    assert glossary_service.get_term_category(term.id) is None


def test_list_and_count_by_category(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "Active Directory")
    ldap = glossary_service.create_term(pid, "LDAP")
    kerberos = glossary_service.create_term(pid, "Kerberos")
    glossary_service.create_term(pid, "Uncategorized")
    glossary_service.set_term_category(ldap.id, category.id)
    glossary_service.set_term_category(kerberos.id, category.id)

    assert glossary_service.count_terms_by_category(category.id) == 2
    assert {t.term for t in glossary_service.list_terms_by_category(category.id)} == {
        "LDAP",
        "Kerberos",
    }


def test_category_profile_isolation(profile_service, glossary_service):
    pid_a = profile_service.create_profile("Cyber Security").id
    pid_b = profile_service.create_profile("Accounting").id
    glossary_service.create_category(pid_a, "Active Directory")
    glossary_service.create_category(pid_b, "Financial")
    assert [c.name for c in glossary_service.list_categories(pid_a)] == ["Active Directory"]
    assert [c.name for c in glossary_service.list_categories(pid_b)] == ["Financial"]


def test_deleting_category_keeps_terms(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "Active Directory")
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.set_term_category(term.id, category.id)

    glossary_service.delete_category(category.id)

    # Term survives; its category is cleared (ON DELETE SET NULL).
    assert glossary_service.get_term(term.id) is not None
    assert glossary_service.get_term_category(term.id) is None


def test_add_existing_term_does_not_duplicate(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "CRTO")
    term = glossary_service.create_term(pid, "LDAP")

    # Assigning an existing term must not create a second term.
    glossary_service.set_term_category(term.id, category.id)

    assert [t.term for t in glossary_service.list_terms(pid)] == ["LDAP"]
    assert glossary_service.get_term_category(term.id).name == "CRTO"
    assert glossary_service.count_terms_by_category(category.id) == 1


def test_move_term_between_categories(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    cat_a = glossary_service.create_category(pid, "Active Directory")
    cat_b = glossary_service.create_category(pid, "CRTO")
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.set_term_category(term.id, cat_a.id)

    # Move to another category (overwrites, exactly one category per term).
    glossary_service.set_term_category(term.id, cat_b.id)

    assert glossary_service.get_term_category(term.id).name == "CRTO"
    assert glossary_service.count_terms_by_category(cat_a.id) == 0
    assert glossary_service.count_terms_by_category(cat_b.id) == 1


def test_delete_term_removes_it(profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_section(term.id, "Definition", "x")

    glossary_service.delete_term(term.id)

    assert glossary_service.get_term(term.id) is None
    assert glossary_service.list_sections(term.id) == []
