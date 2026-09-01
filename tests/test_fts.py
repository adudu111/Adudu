"""FTS5 synchronization consistency tests.

Every searchable change must keep the index in sync. These tests drive changes through the
service layer and assert on search results, so they verify the whole UI→service→repository
→FTS path.
"""

from __future__ import annotations

from cyberglossary.database import fts


def _ids(search_service, query, profile_id=None):
    return {r.term_id for r in search_service.search(query, profile_id)}


def test_new_term_is_searchable(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    assert _ids(search_service, "ldap", pid) == {term.id}


def test_renamed_term_updates_fts(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.rename_term(term.id, "LDAPS")
    assert _ids(search_service, "ldap", pid) == set()
    assert _ids(search_service, "ldaps", pid) == {term.id}


def test_full_name_update(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.set_full_name(term.id, "Lightweight Directory Access Protocol")
    assert _ids(search_service, "lightweight", pid) == {term.id}


def test_alias_add_and_delete(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    alias = glossary_service.add_alias(term.id, "LDPA")
    assert _ids(search_service, "ldpa", pid) == {term.id}

    glossary_service.delete_alias(alias.id)
    assert _ids(search_service, "ldpa", pid) == set()


def test_section_add_edit_delete_rename(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    section = glossary_service.add_section(term.id, "Ports", "389")
    assert _ids(search_service, "389", pid) == {term.id}

    glossary_service.set_section_content(section.id, "636")
    assert _ids(search_service, "389", pid) == set()
    assert _ids(search_service, "636", pid) == {term.id}

    glossary_service.rename_section(section.id, "Network Ports")
    assert _ids(search_service, "network", pid) == {term.id}

    glossary_service.delete_section(section.id)
    assert _ids(search_service, "636", pid) == set()


def test_category_change_updates_fts(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    category = glossary_service.create_category(pid, "Active Directory")
    glossary_service.set_term_category(term.id, category.id)
    assert _ids(search_service, "active", pid) == {term.id}

    glossary_service.rename_category(category.id, "Directory Services")
    assert _ids(search_service, "active", pid) == set()
    assert _ids(search_service, "services", pid) == {term.id}

    glossary_service.delete_category(category.id)
    assert _ids(search_service, "services", pid) == set()
    assert glossary_service.get_term(term.id) is not None  # term survives


def test_tag_change_updates_fts(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.set_term_tags(term.id, ["Protocol"])
    assert _ids(search_service, "protocol", pid) == {term.id}

    tag = glossary_service.get_term_tags(term.id)[0]
    glossary_service.rename_tag(tag.id, "Networking")
    assert _ids(search_service, "protocol", pid) == set()
    assert _ids(search_service, "networking", pid) == {term.id}

    glossary_service.delete_tag(tag.id)
    assert _ids(search_service, "networking", pid) == set()


def test_term_deletion_removes_fts_row(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.delete_term(term.id)
    assert _ids(search_service, "ldap", pid) == set()


def test_profile_deletion_removes_fts_rows(search_service, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    profile_service.delete_profile(pid)
    assert _ids(search_service, "ldap") == set()


def test_duplicate_terms_isolated_by_profile(search_service, profile_service, glossary_service):
    pid_a = profile_service.create_profile("Cyber Security").id
    pid_b = profile_service.create_profile("Accounting").id
    a = glossary_service.create_term(pid_a, "SPN")
    b = glossary_service.create_term(pid_b, "SPN")
    assert _ids(search_service, "spn", pid_a) == {a.id}
    assert _ids(search_service, "spn", pid_b) == {b.id}


def test_fts_rebuild_repopulates(search_service, profile_service, glossary_service, conn):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    # Damage the index, then rebuild.
    conn.execute("DELETE FROM terms_fts")
    assert _ids(search_service, "ldap", pid) == set()

    fts.rebuild(conn)
    assert _ids(search_service, "ldap", pid) == {term.id}


def test_ensure_index_backfills_missing_rows(
    search_service, profile_service, glossary_service, conn
):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    conn.execute("DELETE FROM terms_fts")

    fts.ensure_index(conn)
    assert _ids(search_service, "ldap", pid) == {term.id}


def test_transaction_rollback_keeps_fts_consistent(
    search_service, profile_service, glossary_service, conn
):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    conn.execute("BEGIN")
    conn.execute("UPDATE terms SET full_name = 'Rollback Me' WHERE id = ?", (term.id,))
    fts.sync_term(conn, term.id)
    conn.rollback()

    assert glossary_service.get_term(term.id).full_name == ""
    assert _ids(search_service, "rollback", pid) == set()
    assert _ids(search_service, "ldap", pid) == {term.id}
