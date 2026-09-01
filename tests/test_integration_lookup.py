"""End-to-end lookup integration tests using the same wiring pattern as app.py."""

from __future__ import annotations

from cyberglossary import app
from cyberglossary.services.lookup_service import LookupService


def _lookup(conn, capture=lambda: "LDAP"):
    conn, profile_service, glossary_service, _template, search_service = (
        app._build_services_from_conn(conn)
    )
    return profile_service, glossary_service, search_service, LookupService(
        capture, profile_service, glossary_service, search_service
    )


def test_global_lookup_finds_newly_created_term(conn):
    profile_service, glossary_service, _search, lookup = _lookup(conn)
    pid = profile_service.create_profile("CRTO").id
    glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")

    result = lookup.run()

    assert result.found is True
    assert result.term == "LDAP"
    assert result.full_name == "Lightweight Directory Access Protocol"
    assert profile_service.get_active_profile().name == "CRTO"


def test_lookup_uses_same_active_profile_as_main_ui(conn):
    profile_service, glossary_service, _search, lookup = _lookup(conn)
    profile_service.create_profile("CRTO")
    profile_service.create_profile("Accounting")
    crto = next(p for p in profile_service.list_profiles() if p.name == "CRTO")
    profile_service.set_active_profile(crto.id)
    glossary_service.create_term(crto.id, "LDAP")

    # The lookup resolves via the active profile, exactly as the main UI lists terms.
    assert [t.term for t in glossary_service.list_terms(crto.id)] == ["LDAP"]
    assert lookup.run().found is True


def test_lookup_and_ui_share_database_path(conn, db_path):
    profile_service, glossary_service, _search, lookup = _lookup(conn)
    pid = profile_service.create_profile("CRTO").id
    term = glossary_service.create_term(pid, "LDAP")

    # Both are built from the same connection; a lookup finds what the UI would list.
    assert glossary_service.list_terms(pid)[0].id == term.id
    result = lookup.run()
    assert result.term_id == term.id
