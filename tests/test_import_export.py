"""Tests for profile import/export (JSON + Markdown)."""

from __future__ import annotations

import json

import pytest

from cyberglossary.database import connection, migrations
from cyberglossary.import_export.json_export import export_profile_dict, export_profile_json
from cyberglossary.import_export.json_import import (
    ImportValidationError,
    import_profile,
    parse_json,
)
from cyberglossary.import_export.markdown_export import (
    export_profile_markdown,
    sanitize_filename,
)


def fresh_conn(tmp_path):
    c = connection.connect(tmp_path / "fresh.db")
    migrations.migrate(c)
    return c


def build_rich_profile(profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security", "Blue team", "#123456").id
    category = glossary_service.create_category(pid, "Active Directory")
    glossary_service.create_tag(pid, "Protocol")
    glossary_service.create_tag(pid, "Windows")

    ldap = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.set_term_category(ldap.id, category.id)
    glossary_service.set_term_tags(ldap.id, ["Protocol", "Windows"])
    glossary_service.add_alias(ldap.id, "LDPA")
    glossary_service.add_section(ldap.id, "Definition", "A directory protocol")
    glossary_service.add_section(ldap.id, "Ports", "389")

    kerberos = glossary_service.create_term(pid, "Kerberos")
    glossary_service.add_section(kerberos.id, "AS-REQ", "request")
    glossary_service.add_section(kerberos.id, "TGT", "ticket")

    template = template_service.create_template(pid, "CyberSec Concept")
    template_service.add_section(template.id, "Definition", "hint")
    template_service.add_section(template.id, "Ports")

    return pid


# --- JSON export -----------------------------------------------------------


def test_export_json_structure(profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    data = json.loads(export_profile_json(pid, profile_service, glossary_service, template_service))
    assert data["schema_version"] == 1
    assert data["profile"]["name"] == "Cyber Security"
    assert set(data) >= {"schema_version", "app_version", "exported_at", "profile",
                         "categories", "tags", "templates", "terms"}


def test_export_preserves_data(profile_service, glossary_service, template_service):
    pid = build_rich_profile(profile_service, glossary_service, template_service)
    data = json.loads(export_profile_json(pid, profile_service, glossary_service, template_service))

    assert [c["name"] for c in data["categories"]] == ["Active Directory"]
    assert [t["name"] for t in data["tags"]] == ["Protocol", "Windows"]
    assert [t["name"] for t in data["templates"]] == ["CyberSec Concept"]
    assert [t["term"] for t in data["terms"]] == ["LDAP", "Kerberos"]

    ldap = next(t for t in data["terms"] if t["term"] == "LDAP")
    assert ldap["full_name"] == "Lightweight Directory Access Protocol"
    assert ldap["aliases"] == ["LDPA"]
    assert [s["title"] for s in ldap["sections"]] == ["Definition", "Ports"]
    assert ldap["category_id"] is not None
    assert len(ldap["tag_ids"]) == 2


def test_export_deterministic(profile_service, glossary_service, template_service):
    pid = build_rich_profile(profile_service, glossary_service, template_service)
    a = export_profile_dict(pid, profile_service, glossary_service, template_service,
                            exported_at="2024-01-01T00:00:00")
    b = export_profile_dict(pid, profile_service, glossary_service, template_service,
                            exported_at="2024-01-01T00:00:00")
    assert a == b


# --- JSON import validation ------------------------------------------------


def test_parse_invalid_json_raises():
    with pytest.raises(ImportValidationError):
        parse_json("{ not valid")


def test_validate_top_level_not_dict():
    from cyberglossary.import_export.json_import import validate_import

    with pytest.raises(ImportValidationError):
        validate_import([])


def test_validate_unsupported_version():
    with pytest.raises(ImportValidationError) as exc:
        from cyberglossary.import_export.json_import import validate_import

        validate_import({"schema_version": 999, "profile": {"name": "X"}})
    assert "schema_version" in str(exc.value)


def test_validate_missing_name():
    with pytest.raises(ImportValidationError):
        from cyberglossary.import_export.json_import import validate_import

        validate_import({"schema_version": 1, "profile": {}})


def test_validate_invalid_category_reference():
    from cyberglossary.import_export.json_import import validate_import

    data = {
        "schema_version": 1,
        "profile": {"name": "X"},
        "categories": [],
        "tags": [],
        "templates": [],
        "terms": [{"id": 1, "term": "LDAP", "category_id": 42}],
    }
    with pytest.raises(ImportValidationError) as exc:
        validate_import(data)
    assert "category_id" in str(exc.value)


def test_validate_duplicate_term_names():
    from cyberglossary.import_export.json_import import validate_import

    data = {
        "schema_version": 1,
        "profile": {"name": "X"},
        "terms": [{"id": 1, "term": "LDAP"}, {"id": 2, "term": "ldap"}],
    }
    with pytest.raises(ImportValidationError):
        validate_import(data)


# --- JSON import behavior --------------------------------------------------


def _doc(profile_name="Imported", terms=None, categories=None, tags=None, templates=None):
    return {
        "schema_version": 1,
        "profile": {"name": profile_name, "description": "d", "color": None},
        "categories": categories or [],
        "tags": tags or [],
        "templates": templates or [],
        "terms": terms or [],
    }


def test_import_merge_creates_profile(conn):
    result = import_profile(
        conn,
        _doc(terms=[{"id": 1, "term": "LDAP", "full_name": "LDAP Protocol"}]),
        "merge",
    )
    assert result.terms_imported == 1
    assert result.profile_name == "Imported"
    row = conn.execute("SELECT COUNT(*) AS n FROM terms").fetchone()
    assert row["n"] == 1


def test_import_merge_skips_conflicting_terms(conn, profile_service, glossary_service):
    pid = profile_service.create_profile("Imported").id
    glossary_service.create_term(pid, "LDAP")

    result = import_profile(
        conn,
        _doc(terms=[{"id": 1, "term": "LDAP"}, {"id": 2, "term": "Kerberos"}]),
        "merge",
    )
    assert result.terms_imported == 1
    assert result.terms_skipped == ["LDAP"]


def test_import_replace_deletes_target(conn, profile_service, glossary_service):
    profile_service.create_profile("Imported")
    glossary_service.create_term(1, "OLD")

    result = import_profile(
        conn,
        _doc(terms=[{"id": 1, "term": "LDAP"}]),
        "replace",
    )
    assert result.replaced is True
    names = [r["term"] for r in conn.execute("SELECT term FROM terms").fetchall()]
    assert names == ["LDAP"]


def test_import_replace_preserves_other_profiles(conn, profile_service):
    profile_service.create_profile("Keep Me")
    profile_service.create_profile("Imported")

    import_profile(conn, _doc(terms=[{"id": 1, "term": "LDAP"}]), "replace")

    names = [r["name"] for r in conn.execute("SELECT name FROM profiles").fetchall()]
    assert "Keep Me" in names
    assert "Imported" in names


def test_import_id_remapping(conn):
    # Pre-existing profile consumes ids; imported references must be remapped.
    conn.execute(
        "INSERT INTO profiles (name, sort_order, created_at, updated_at) VALUES ('Other', 0, 'now', 'now')"
    )
    conn.execute("INSERT INTO categories (profile_id, name, sort_order) VALUES (1, 'X', 0)")
    conn.commit()

    data = _doc(
        categories=[{"id": 1, "name": "Active Directory"}],
        terms=[{"id": 10, "term": "LDAP", "category_id": 1}],
    )
    result = import_profile(conn, data, "merge")

    ldap_category = conn.execute(
        "SELECT c.id FROM terms t JOIN categories c ON c.id = t.category_id WHERE t.term = 'LDAP'"
    ).fetchone()
    assert ldap_category is not None
    assert ldap_category["id"] != 1  # remapped to a new local id
    assert result.terms_imported == 1


def test_import_rollback_on_failure(conn, monkeypatch):
    from cyberglossary.database import fts as fts_module

    real = fts_module.sync_term
    calls = {"n": 0}

    def flaky(conn, term_id):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("boom")
        return real(conn, term_id)

    monkeypatch.setattr(fts_module, "sync_term", flaky)
    data = _doc(terms=[{"id": 1, "term": "A"}, {"id": 2, "term": "B"}])

    with pytest.raises(RuntimeError):
        import_profile(conn, data, "merge")

    assert conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM terms").fetchone()["n"] == 0


# --- round trip ------------------------------------------------------------


def test_round_trip(tmp_path, profile_service, glossary_service, template_service):
    pid = build_rich_profile(profile_service, glossary_service, template_service)
    text = export_profile_json(pid, profile_service, glossary_service, template_service)

    target = fresh_conn(tmp_path)
    import_profile(target, parse_json(text), "merge")

    # profile
    p = target.execute("SELECT name, description, color FROM profiles").fetchone()
    assert p["name"] == "Cyber Security"
    assert p["description"] == "Blue team"
    assert p["color"] == "#123456"

    # categories / tags / templates
    assert [r["name"] for r in target.execute("SELECT name FROM categories")] == ["Active Directory"]
    assert [r["name"] for r in target.execute("SELECT name FROM tags ORDER BY name")] == [
        "Protocol", "Windows",
    ]
    assert [r["name"] for r in target.execute("SELECT name FROM templates")] == ["CyberSec Concept"]
    tpl_sections = target.execute(
        "SELECT title FROM template_sections ts JOIN templates t ON t.id = ts.template_id "
        "ORDER BY ts.sort_order"
    ).fetchall()
    assert [r["title"] for r in tpl_sections] == ["Definition", "Ports"]

    # terms
    terms = target.execute("SELECT id, term, full_name FROM terms ORDER BY term").fetchall()
    assert [(r["term"], r["full_name"]) for r in terms] == [
        ("Kerberos", ""),
        ("LDAP", "Lightweight Directory Access Protocol"),
    ]

    # LDAP details
    ldap = target.execute("SELECT id FROM terms WHERE term = 'LDAP'").fetchone()
    ldap_sections = target.execute(
        "SELECT title, content FROM sections WHERE term_id = ? ORDER BY sort_order", (ldap["id"],)
    ).fetchall()
    assert [(s["title"], s["content"]) for s in ldap_sections] == [
        ("Definition", "A directory protocol"),
        ("Ports", "389"),
    ]
    aliases = target.execute(
        "SELECT alias FROM aliases WHERE term_id = ?", (ldap["id"],)
    ).fetchall()
    assert [a["alias"] for a in aliases] == ["LDPA"]
    category = target.execute(
        "SELECT c.name FROM terms t JOIN categories c ON c.id = t.category_id WHERE t.id = ?",
        (ldap["id"],),
    ).fetchone()
    assert category["name"] == "Active Directory"
    tags = target.execute(
        "SELECT g.name FROM term_tags tt JOIN tags g ON g.id = tt.tag_id WHERE tt.term_id = ? "
        "ORDER BY g.name",
        (ldap["id"],),
    ).fetchall()
    assert [t["name"] for t in tags] == ["Protocol", "Windows"]


# --- Markdown --------------------------------------------------------------


def test_markdown_one_file_per_term(profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    glossary_service.create_term(pid, "Kerberos")

    files = export_profile_markdown(pid, profile_service, glossary_service, template_service)
    assert [f for f, _ in files] == ["LDAP.md", "Kerberos.md"]


def test_markdown_section_order_and_titles(profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_section(term.id, "Ports", "389")
    glossary_service.add_section(term.id, "Attack Techniques", "x")

    files = export_profile_markdown(pid, profile_service, glossary_service, template_service)
    content = files[0][1]
    assert "## Ports" in content
    assert "## Attack Techniques" in content
    assert content.index("## Ports") < content.index("## Attack Techniques")


def test_markdown_metadata(profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    category = glossary_service.create_category(pid, "Active Directory")
    glossary_service.set_term_category(term.id, category.id)
    glossary_service.set_term_tags(term.id, ["Protocol"])
    glossary_service.add_alias(term.id, "LDPA")

    files = export_profile_markdown(pid, profile_service, glossary_service, template_service)
    content = files[0][1]
    assert "# LDAP" in content
    assert "Lightweight Directory Access Protocol" in content
    assert "Active Directory" in content
    assert "Protocol" in content
    assert "LDPA" in content


def test_sanitize_filename_invalid_chars():
    assert sanitize_filename("LDAP:Ports?") == "LDAP_Ports_"
    assert sanitize_filename("a/b\\c") == "a_b_c"


def test_sanitize_filename_reserved_and_trailing():
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("LDAP.") == "LDAP"


def test_sanitize_filename_long():
    assert len(sanitize_filename("x" * 500)) == 120


def test_markdown_duplicate_filenames(profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "a:b")
    glossary_service.create_term(pid, "a?b")

    files = export_profile_markdown(pid, profile_service, glossary_service, template_service)
    names = [f for f, _ in files]
    assert names == ["a_b.md", "a_b (2).md"]
