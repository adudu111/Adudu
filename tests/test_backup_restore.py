"""Tests for database backup and restore."""

from __future__ import annotations

import re
import sqlite3

import pytest

from cyberglossary.database.repositories import SearchRepository
from cyberglossary.services.backup_service import BackupError, BackupService, verify_database
from cyberglossary.services.search_service import SearchService


def _source(tmp_path):
    from cyberglossary.database import connection, migrations

    db_path = tmp_path / "app.db"
    conn = connection.connect(db_path)
    migrations.migrate(conn)
    return conn, db_path


# --- backup ----------------------------------------------------------------


def test_backup_creates_file(conn, db_path, tmp_path):
    bs = BackupService(conn, db_path)
    dest = tmp_path / "backups"
    backup = bs.create_backup(dest)
    assert backup.exists()
    assert backup.parent == dest
    assert re.match(r"cyberglossary-\d{8}-\d{6}\.db$", backup.name)


def test_backup_filename_unique(conn, db_path, tmp_path):
    bs = BackupService(conn, db_path)
    dest = tmp_path / "backups"
    first = bs.create_backup(dest)
    second = bs.create_backup(dest)
    assert first != second


def test_backup_destination_created(conn, db_path, tmp_path):
    bs = BackupService(conn, db_path)
    dest = tmp_path / "nested" / "backups"
    bs.create_backup(dest)
    assert dest.is_dir()


def test_backup_contains_data(conn, db_path, tmp_path, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    check = sqlite3.connect(str(backup))
    try:
        assert check.execute("SELECT term FROM terms").fetchone()[0] == "LDAP"
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()


def test_verify_database_rejects_invalid(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not a sqlite database")
    with pytest.raises(BackupError):
        verify_database(bad)


# --- restore validation ----------------------------------------------------


def test_restore_invalid_file(conn, db_path, tmp_path):
    bs = BackupService(conn, db_path)
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"garbage")
    with pytest.raises(BackupError):
        bs.restore(bad)


def test_restore_corrupted_database(conn, db_path, tmp_path, profile_service, glossary_service):
    profile_service.create_profile("Cyber Security")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    data = bytearray(backup.read_bytes())
    data[:100] = b"\xff" * 100
    backup.write_bytes(bytes(data))

    with pytest.raises(BackupError):
        bs.restore(backup)


def test_restore_wrong_schema_version(conn, db_path, tmp_path):
    bs = BackupService(conn, db_path)
    bad = tmp_path / "plain.db"
    c = sqlite3.connect(str(bad))
    c.close()  # user_version == 0
    with pytest.raises(BackupError):
        bs.restore(bad)


def test_restore_missing_table(conn, db_path, tmp_path):
    bs = BackupService(conn, db_path)
    bad = tmp_path / "missing.db"
    c = sqlite3.connect(str(bad))
    c.execute("PRAGMA user_version = 1")
    c.execute("CREATE TABLE profiles (id INTEGER PRIMARY KEY)")
    c.commit()
    c.close()
    with pytest.raises(BackupError) as exc:
        bs.restore(bad)
    assert "Missing required tables" in str(exc.value)


# --- restore behavior ------------------------------------------------------


def test_restore_replaces_target(conn, db_path, tmp_path, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    glossary_service.delete_term(glossary_service.list_terms(pid)[0].id)
    assert conn.execute("SELECT COUNT(*) AS n FROM terms").fetchone()["n"] == 0

    new_conn = bs.restore(backup, safety_dir=tmp_path / "safety")
    assert new_conn.execute("SELECT term FROM terms").fetchone()["term"] == "LDAP"


def test_restore_creates_safety_backup(conn, db_path, tmp_path, profile_service, glossary_service):
    profile_service.create_profile("Cyber Security")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    bs.restore(backup, safety_dir=tmp_path / "safety")

    safety = list((tmp_path / "safety").glob("pre-restore-*.db"))
    assert safety


def test_safety_backup_failure_aborts(conn, db_path, tmp_path, profile_service, glossary_service, monkeypatch):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    def boom(*_args, **_kwargs):
        raise BackupError("safety failed")

    monkeypatch.setattr(bs, "create_backup", boom)
    with pytest.raises(BackupError):
        bs.restore(backup)

    # Connection still open and data intact (nothing was touched).
    assert conn.execute("SELECT COUNT(*) AS n FROM terms").fetchone()["n"] == 1


def test_failed_restore_leaves_db_intact(conn, db_path, tmp_path, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    bs = BackupService(conn, db_path)

    bad = tmp_path / "bad.db"
    bad.write_bytes(b"garbage")
    with pytest.raises(BackupError):
        bs.restore(bad)

    assert db_path.exists()
    assert conn.execute("SELECT COUNT(*) AS n FROM terms").fetchone()["n"] == 1


def test_reopened_connection_works(conn, db_path, tmp_path, profile_service, glossary_service):
    profile_service.create_profile("Cyber Security")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    new_conn = bs.restore(backup, safety_dir=tmp_path / "safety")
    assert new_conn.execute("SELECT 1").fetchone()[0] == 1
    assert new_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_fts_works_after_restore(conn, db_path, tmp_path, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")

    new_conn = bs.restore(backup, safety_dir=tmp_path / "safety")
    search = SearchService(SearchRepository(new_conn))
    assert [r.term for r in search.search("ldap", None)] == ["LDAP"]


def test_round_trip(conn, db_path, tmp_path, profile_service, glossary_service, template_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "Active Directory")
    term = glossary_service.create_term(pid, "LDAP", "LDAP Protocol")
    glossary_service.set_term_category(term.id, category.id)
    glossary_service.add_section(term.id, "Ports", "389")
    template = template_service.create_template(pid, "Concept")
    template_service.add_section(template.id, "Definition")

    bs = BackupService(conn, db_path)
    backup = bs.create_backup(tmp_path / "backups")
    new_conn = bs.restore(backup, safety_dir=tmp_path / "safety")

    assert new_conn.execute("SELECT name FROM categories").fetchone()["name"] == "Active Directory"
    assert new_conn.execute("SELECT name FROM templates").fetchone()["name"] == "Concept"
    section = new_conn.execute("SELECT title, content FROM sections").fetchone()
    assert (section["title"], section["content"]) == ("Ports", "389")
    term_row = new_conn.execute("SELECT term, full_name FROM terms").fetchone()
    assert (term_row["term"], term_row["full_name"]) == ("LDAP", "LDAP Protocol")
    assert new_conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
