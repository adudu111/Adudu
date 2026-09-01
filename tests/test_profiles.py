"""Tests for profiles (repository + service)."""

from __future__ import annotations

import sqlite3

import pytest

from cyberglossary.database import connection, migrations
from cyberglossary.database.repositories import (
    DuplicateProfileNameError,
    ProfileNotFoundError,
    ProfileRepository,
    SettingsRepository,
)
from cyberglossary.services.profile_service import ACTIVE_PROFILE_KEY, ProfileService


def make_service(conn: sqlite3.Connection) -> ProfileService:
    return ProfileService(ProfileRepository(conn), SettingsRepository(conn))


# --- creation / retrieval -------------------------------------------------


def test_create_and_get(conn):
    svc = make_service(conn)
    profile = svc.create_profile("Cyber Security", "Blue team concepts", "#ff0000")
    assert profile.id is not None
    assert profile.name == "Cyber Security"
    assert profile.description == "Blue team concepts"
    assert profile.color == "#ff0000"

    fetched = svc.get_profile(profile.id)
    assert fetched == profile


def test_create_defaults(conn):
    svc = make_service(conn)
    profile = svc.create_profile("Accounting")
    assert profile.description == ""
    assert profile.color is None


def test_create_rejects_empty_name(conn):
    svc = make_service(conn)
    with pytest.raises(ValueError):
        svc.create_profile("   ")


def test_duplicate_name_raises(conn):
    svc = make_service(conn)
    svc.create_profile("Cyber Security")
    with pytest.raises(DuplicateProfileNameError):
        svc.create_profile("Cyber Security")


def test_duplicate_name_is_case_insensitive(conn):
    svc = make_service(conn)
    svc.create_profile("Cyber Security")
    with pytest.raises(DuplicateProfileNameError):
        svc.create_profile("cyber security")


# --- list / ordering -------------------------------------------------------


def test_list_profiles_in_creation_order(conn):
    svc = make_service(conn)
    first = svc.create_profile("Networking")
    second = svc.create_profile("Accounting")
    third = svc.create_profile("English")
    names = [p.name for p in svc.list_profiles()]
    assert names == ["Networking", "Accounting", "English"]
    assert [p.id for p in svc.list_profiles()] == [first.id, second.id, third.id]


def test_reorder_profiles(conn):
    svc = make_service(conn)
    a = svc.create_profile("A")
    b = svc.create_profile("B")
    c = svc.create_profile("C")

    svc.reorder_profiles([c.id, a.id, b.id])
    assert [p.name for p in svc.list_profiles()] == ["C", "A", "B"]


# --- edit ------------------------------------------------------------------


def test_rename(conn):
    svc = make_service(conn)
    profile = svc.create_profile("Networking")
    updated = svc.rename_profile(profile.id, "Networking Advanced")
    assert updated.name == "Networking Advanced"
    assert updated.id == profile.id


def test_rename_duplicate_raises(conn):
    svc = make_service(conn)
    svc.create_profile("Networking")
    other = svc.create_profile("Accounting")
    with pytest.raises(DuplicateProfileNameError):
        svc.rename_profile(other.id, "networking")


def test_rename_missing_raises(conn):
    svc = make_service(conn)
    with pytest.raises(ProfileNotFoundError):
        svc.rename_profile(999, "Ghost")


def test_set_description_and_color(conn):
    svc = make_service(conn)
    profile = svc.create_profile("English")
    with_desc = svc.set_description(profile.id, "Vocabulary")
    with_color = svc.set_color(profile.id, "#00ff00")
    assert with_desc.description == "Vocabulary"
    assert with_color.color == "#00ff00"


def test_clear_color(conn):
    svc = make_service(conn)
    profile = svc.create_profile("English", color="#123456")
    cleared = svc.set_color(profile.id, None)
    assert cleared.color is None


# --- delete ----------------------------------------------------------------


def test_delete_profile(conn):
    svc = make_service(conn)
    profile = svc.create_profile("English")
    svc.delete_profile(profile.id)
    assert svc.get_profile(profile.id) is None


def test_delete_missing_raises(conn):
    svc = make_service(conn)
    with pytest.raises(ProfileNotFoundError):
        svc.delete_profile(12345)


# --- active profile --------------------------------------------------------


def test_first_profile_becomes_active(conn):
    svc = make_service(conn)
    profile = svc.create_profile("Cyber Security")
    assert svc.get_active_profile_id() == profile.id
    assert svc.get_active_profile() == profile


def test_set_active_profile(conn):
    svc = make_service(conn)
    svc.create_profile("Cyber Security")
    second = svc.create_profile("Accounting")
    assert svc.get_active_profile_id() != second.id

    svc.set_active_profile(second.id)
    assert svc.get_active_profile_id() == second.id
    assert svc.get_active_profile() == second


def test_set_active_missing_raises(conn):
    svc = make_service(conn)
    with pytest.raises(ProfileNotFoundError):
        svc.set_active_profile(999)


def test_delete_active_profile_clears_active(conn):
    svc = make_service(conn)
    profile = svc.create_profile("Cyber Security")
    svc.delete_profile(profile.id)
    assert svc.get_active_profile_id() is None
    assert svc.get_active_profile() is None


def test_delete_active_profile_selects_another(conn):
    svc = make_service(conn)
    first = svc.create_profile("Cyber Security")
    second = svc.create_profile("Accounting")
    assert svc.get_active_profile_id() == first.id

    svc.delete_profile(first.id)

    assert svc.get_active_profile_id() == second.id
    assert svc.get_active_profile() == second


def test_auto_selected_active_persists_reconnect(db_path):
    conn1 = connection.connect(db_path)
    migrations.migrate(conn1)
    svc = make_service(conn1)
    first = svc.create_profile("Cyber Security")
    second = svc.create_profile("Accounting")
    svc.delete_profile(first.id)
    conn1.close()

    conn2 = connection.connect(db_path)
    repo = SettingsRepository(conn2)
    assert repo.get(ACTIVE_PROFILE_KEY) == str(second.id)
    conn2.close()


def test_active_profile_survives_reopen(db_path):
    conn1 = connection.connect(db_path)
    migrations.migrate(conn1)
    svc = make_service(conn1)
    svc.create_profile("Cyber Security")
    second = svc.create_profile("Accounting")
    svc.set_active_profile(second.id)
    conn1.close()

    conn2 = connection.connect(db_path)
    repo = SettingsRepository(conn2)
    assert repo.get(ACTIVE_PROFILE_KEY) == str(second.id)
    conn2.close()


# --- cascade (FR-03): deleting a profile removes all children --------------
# Uses raw SQL to seed child rows directly; child *services* arrive in later phases.


def _seed_children(conn: sqlite3.Connection, profile_id: int) -> None:
    conn.execute(
        "INSERT INTO categories (profile_id, name, sort_order) VALUES (?, 'Active Directory', 0)",
        (profile_id,),
    )
    tag_id = conn.execute(
        "INSERT INTO tags (profile_id, name) VALUES (?, 'Protocol')", (profile_id,)
    ).lastrowid
    term_id = conn.execute(
        "INSERT INTO terms (profile_id, term, full_name, created_at, updated_at) "
        "VALUES (?, 'LDAP', 'Lightweight Directory Access Protocol', 'now', 'now')",
        (profile_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO sections (term_id, title, content, sort_order, created_at, updated_at) "
        "VALUES (?, 'Definition', 'x', 0, 'now', 'now')",
        (term_id,),
    )
    conn.execute(
        "INSERT INTO aliases (term_id, alias, created_at) VALUES (?, 'LDPA', 'now')", (term_id,)
    )
    conn.execute(
        "INSERT INTO term_tags (term_id, tag_id) VALUES (?, ?)", (term_id, tag_id)
    )
    template_id = conn.execute(
        "INSERT INTO templates (profile_id, name, created_at, updated_at) VALUES (?, 'CyberSec', 'now', 'now')",
        (profile_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO template_sections (template_id, title, sort_order) VALUES (?, 'Definition', 0)",
        (template_id,),
    )
    conn.commit()


def test_deleting_profile_cascades_to_children(conn):
    svc = make_service(conn)
    profile = svc.create_profile("Cyber Security")
    _seed_children(conn, profile.id)

    svc.delete_profile(profile.id)

    counts = {
        table: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        for table in (
            "categories",
            "tags",
            "terms",
            "sections",
            "aliases",
            "term_tags",
            "templates",
            "template_sections",
        )
    }
    assert all(n == 0 for n in counts.values())
