"""Lightweight Qt tests for the main UI (offscreen, temp DB, no real user data)."""

from __future__ import annotations

import pytest

from cyberglossary.ui.list_utils import visible_texts
from cyberglossary.ui.profile_selector import ProfileSelector
from cyberglossary.ui.term_editor import TermEditor
from cyberglossary.ui.term_list import TermList


def _list_texts(widget) -> list[str]:
    return visible_texts(widget.list)


# --- profile selector -----------------------------------------------------


def test_profile_selector_lists_and_selects(qapp, profile_service):
    first = profile_service.create_profile("Cyber Security")
    second = profile_service.create_profile("Accounting")

    selector = ProfileSelector(profile_service)

    assert selector.combo.count() == 2
    assert selector.current_profile_id() == first.id  # first created is active

    selector.select_profile(second.id)
    assert profile_service.get_active_profile_id() == second.id


def test_profile_selector_create_profile(qapp, profile_service):
    selector = ProfileSelector(profile_service)
    selector.create_profile("Networking")

    assert selector.combo.count() == 1
    assert profile_service.get_active_profile_id() is not None


def test_profile_selector_rename_and_delete(qapp, profile_service):
    profile_service.create_profile("Cyber Security")
    profile = profile_service.create_profile("Accounting")

    selector = ProfileSelector(profile_service)
    selector.select_profile(profile.id)
    selector.rename_current("Accounting 2")
    assert profile_service.get_active_profile().name == "Accounting 2"

    selector.delete_current()
    assert selector.combo.count() == 1


# --- term list ------------------------------------------------------------


def test_term_list_lists_terms(qapp, profile_service, glossary_service, search_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP")
    glossary_service.create_term(pid, "Kerberos")

    term_list = TermList(glossary_service, search_service)
    term_list.set_profile(pid)

    assert _list_texts(term_list) == ["LDAP", "Kerberos"]


def test_term_list_add_term(qapp, profile_service, glossary_service, search_service):
    pid = profile_service.create_profile("Cyber Security").id
    term_list = TermList(glossary_service, search_service)
    term_list.set_profile(pid)

    term = term_list.add_term("GPO")

    assert term.term == "GPO"
    assert term_list.list.count() == 1
    assert term_list.selected_term_id() == term.id


def test_term_list_search_uses_service(qapp, profile_service, glossary_service, search_service):
    pid = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.create_term(pid, "Kerberos")

    term_list = TermList(glossary_service, search_service)
    term_list.set_profile(pid)

    term_list.set_search_text("ldap")
    term_list._reload_list()

    assert _list_texts(term_list) == ["LDAP"]

    term_list.set_search_text("zzz")
    term_list._reload_list()
    assert _list_texts(term_list) == ["No matching terms found."]


# --- term editor ----------------------------------------------------------


def test_term_editor_renders_sections_dynamically(qapp, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_section(term.id, "Definition", "A directory protocol")
    glossary_service.add_section(term.id, "Ports", "389")

    editor = TermEditor(glossary_service)
    editor.set_term(term.id)

    assert [s.title_edit.text() for s in editor.sections] == ["Definition", "Ports"]


def test_term_editor_add_and_delete_section(qapp, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    editor = TermEditor(glossary_service)
    editor.set_term(term.id)

    editor.add_section("My Notes")
    assert [s.title_edit.text() for s in editor.sections] == ["My Notes"]

    section = glossary_service.list_sections(term.id)[0]
    editor.delete_section(section.id)
    assert glossary_service.list_sections(term.id) == []


def test_term_editor_reorder_sections(qapp, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    glossary_service.add_section(term.id, "A")
    glossary_service.add_section(term.id, "B")
    glossary_service.add_section(term.id, "C")

    editor = TermEditor(glossary_service)
    editor.set_term(term.id)

    c_id = glossary_service.list_sections(term.id)[2].id
    editor.move_section(c_id, -1)
    assert [s.title for s in glossary_service.list_sections(term.id)] == ["A", "C", "B"]

    editor.move_section(c_id, -1)
    assert [s.title for s in glossary_service.list_sections(term.id)] == ["C", "A", "B"]


def test_term_editor_edit_full_name_and_aliases(qapp, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    editor = TermEditor(glossary_service)
    editor.set_term(term.id)

    editor.set_full_name("Lightweight Directory Access Protocol")
    assert glossary_service.get_term(term.id).full_name == "Lightweight Directory Access Protocol"

    alias = editor.add_alias("LDPA")
    assert [a.alias for a in glossary_service.list_aliases(term.id)] == ["LDPA"]

    editor.remove_alias(alias.id)
    assert glossary_service.list_aliases(term.id) == []


def test_term_editor_rename_emits_signal(qapp, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    editor = TermEditor(glossary_service)
    editor.set_term(term.id)

    emitted = []
    editor.term_renamed.connect(emitted.append)
    editor.rename("LDAPS")

    assert glossary_service.get_term(term.id).term == "LDAPS"
    assert emitted == [term.id]


def test_term_editor_rejects_empty_section_title(qapp, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")
    editor = TermEditor(glossary_service)
    editor.set_term(term.id)
    with pytest.raises(ValueError):
        editor.add_section("   ")


# --- main window integration ---------------------------------------------


def test_profile_switch_updates_term_list(window, profile_service, glossary_service):
    pid_a = profile_service.create_profile("Cyber Security").id
    glossary_service.create_term(pid_a, "LDAP")
    pid_b = profile_service.create_profile("Accounting").id
    glossary_service.create_term(pid_b, "ROA")

    window.term_list.set_profile(pid_a)
    assert _list_texts(window.term_list) == ["LDAP"]

    window.profile_selector.select_profile(pid_b)
    assert _list_texts(window.term_list) == ["ROA"]


def test_main_window_constructs_and_selects_term(window, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    window.term_list.set_profile(pid)
    window.term_list.select(term.id)

    assert window.term_editor.name_edit.text() == "LDAP"
