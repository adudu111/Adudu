"""Tests for templates (CRUD, section ordering, duplication, apply-to-term)."""

from __future__ import annotations

import pytest

from cyberglossary.database.repositories import (
    DuplicateTemplateNameError,
    DuplicateTermNameError,
    ProfileNotFoundError,
    TemplateNotFoundError,
    TemplateSectionNotFoundError,
)


def _profile(profile_service):
    return profile_service.create_profile("Cyber Security")


def _template(template_service, profile_service):
    pid = _profile(profile_service).id
    return template_service.create_template(pid, "Cyber Security Concept")


# --- template CRUD --------------------------------------------------------


def test_create_and_get(template_service, profile_service):
    pid = _profile(profile_service).id
    template = template_service.create_template(pid, "Cyber Security Concept", "Blue team")
    assert template.name == "Cyber Security Concept"
    assert template.description == "Blue team"
    assert template_service.get_template(template.id) == template


def test_create_defaults(template_service, profile_service):
    pid = _profile(profile_service).id
    template = template_service.create_template(pid, "Concept")
    assert template.description == ""


def test_create_rejects_empty_name(template_service, profile_service):
    pid = _profile(profile_service).id
    with pytest.raises(ValueError):
        template_service.create_template(pid, "   ")


def test_create_in_missing_profile_raises(template_service):
    with pytest.raises(ProfileNotFoundError):
        template_service.create_template(999, "Concept")


def test_duplicate_name_within_profile_raises(template_service, profile_service):
    pid = _profile(profile_service).id
    template_service.create_template(pid, "Concept")
    with pytest.raises(DuplicateTemplateNameError):
        template_service.create_template(pid, "Concept")


def test_duplicate_name_case_insensitive(template_service, profile_service):
    pid = _profile(profile_service).id
    template_service.create_template(pid, "Concept")
    with pytest.raises(DuplicateTemplateNameError):
        template_service.create_template(pid, "concept")


def test_same_name_allowed_in_different_profiles(template_service, profile_service):
    pid_a = _profile(profile_service).id
    pid_b = profile_service.create_profile("Accounting").id
    template_service.create_template(pid_a, "Concept")
    other = template_service.create_template(pid_b, "Concept")
    assert other.profile_id == pid_b


def test_list_templates_in_creation_order(template_service, profile_service):
    pid = _profile(profile_service).id
    a = template_service.create_template(pid, "A")
    b = template_service.create_template(pid, "B")
    c = template_service.create_template(pid, "C")
    assert [t.name for t in template_service.list_templates(pid)] == ["A", "B", "C"]
    assert [t.id for t in template_service.list_templates(pid)] == [a.id, b.id, c.id]


def test_list_templates_profile_scoped(template_service, profile_service):
    pid_a = _profile(profile_service).id
    pid_b = profile_service.create_profile("Accounting").id
    template_service.create_template(pid_a, "Concept")
    assert template_service.list_templates(pid_b) == []


def test_rename_template(template_service, profile_service):
    template = _template(template_service, profile_service)
    updated = template_service.rename_template(template.id, "Protocol")
    assert updated.name == "Protocol"


def test_rename_duplicate_raises(template_service, profile_service):
    template = _template(template_service, profile_service)
    other = template_service.create_template(template.profile_id, "Other")
    with pytest.raises(DuplicateTemplateNameError):
        template_service.rename_template(other.id, "cyber security concept")


def test_rename_missing_raises(template_service):
    with pytest.raises(TemplateNotFoundError):
        template_service.rename_template(999, "X")


def test_set_description(template_service, profile_service):
    template = _template(template_service, profile_service)
    updated = template_service.set_description(template.id, "New description")
    assert updated.description == "New description"


def test_delete_template_cascades_sections(template_service, profile_service):
    template = _template(template_service, profile_service)
    template_service.add_section(template.id, "Definition")
    template_service.delete_template(template.id)
    assert template_service.get_template(template.id) is None
    assert template_service.list_sections(template.id) == []


def test_delete_missing_raises(template_service):
    with pytest.raises(TemplateNotFoundError):
        template_service.delete_template(12345)


def test_reorder_templates(template_service, profile_service):
    pid = _profile(profile_service).id
    a = template_service.create_template(pid, "A")
    b = template_service.create_template(pid, "B")
    c = template_service.create_template(pid, "C")
    template_service.reorder_templates(pid, [c.id, a.id, b.id])
    assert [t.name for t in template_service.list_templates(pid)] == ["C", "A", "B"]


# --- template section CRUD ------------------------------------------------


def test_add_section_and_list(template_service, profile_service):
    template = _template(template_service, profile_service)
    section = template_service.add_section(template.id, "Definition", "What is it?")
    assert section.title == "Definition"
    assert section.placeholder == "What is it?"
    assert [s.id for s in template_service.list_sections(template.id)] == [section.id]


def test_sections_are_dynamic_titles(template_service, profile_service):
    template = _template(template_service, profile_service)
    for title in ("Definition", "How it works", "Ports", "Attack Techniques", "My Notes"):
        template_service.add_section(template.id, title)
    assert [s.title for s in template_service.list_sections(template.id)] == [
        "Definition",
        "How it works",
        "Ports",
        "Attack Techniques",
        "My Notes",
    ]


def test_sections_order_preserved(template_service, profile_service):
    template = _template(template_service, profile_service)
    template_service.add_section(template.id, "Definition")
    template_service.add_section(template.id, "Ports")
    template_service.add_section(template.id, "My Notes")
    assert [s.title for s in template_service.list_sections(template.id)] == [
        "Definition",
        "Ports",
        "My Notes",
    ]


def test_set_section_title(template_service, profile_service):
    template = _template(template_service, profile_service)
    section = template_service.add_section(template.id, "Definition")
    updated = template_service.set_section_title(section.id, "What it is")
    assert updated.title == "What it is"


def test_set_section_placeholder(template_service, profile_service):
    template = _template(template_service, profile_service)
    section = template_service.add_section(template.id, "Ports")
    updated = template_service.set_section_placeholder(section.id, "e.g. 389")
    assert updated.placeholder == "e.g. 389"


def test_reorder_sections(template_service, profile_service):
    template = _template(template_service, profile_service)
    a = template_service.add_section(template.id, "A")
    b = template_service.add_section(template.id, "B")
    c = template_service.add_section(template.id, "C")
    template_service.reorder_sections(template.id, [c.id, a.id, b.id])
    assert [s.title for s in template_service.list_sections(template.id)] == ["C", "A", "B"]


def test_delete_section(template_service, profile_service):
    template = _template(template_service, profile_service)
    section = template_service.add_section(template.id, "Definition")
    template_service.delete_section(section.id)
    assert template_service.list_sections(template.id) == []


def test_delete_missing_section_raises(template_service):
    with pytest.raises(TemplateSectionNotFoundError):
        template_service.delete_section(999)


def test_add_section_to_missing_template_raises(template_service):
    with pytest.raises(TemplateNotFoundError):
        template_service.add_section(999, "Definition")


def test_add_section_rejects_empty_title(template_service, profile_service):
    template = _template(template_service, profile_service)
    with pytest.raises(ValueError):
        template_service.add_section(template.id, "   ")


# --- template duplication -------------------------------------------------


def test_duplicate_copies_sections(template_service, profile_service):
    template = _template(template_service, profile_service)
    template_service.add_section(template.id, "Definition", "hint1")
    template_service.add_section(template.id, "Ports", "hint2")

    copy = template_service.duplicate_template(template.id)

    assert copy.id != template.id
    assert copy.name == "Cyber Security Concept (copy)"
    copied = template_service.list_sections(copy.id)
    assert [(s.title, s.placeholder) for s in copied] == [
        ("Definition", "hint1"),
        ("Ports", "hint2"),
    ]


def test_duplicate_generates_unique_name(template_service, profile_service):
    template = _template(template_service, profile_service)
    first = template_service.duplicate_template(template.id)
    second = template_service.duplicate_template(template.id)
    assert first.name == "Cyber Security Concept (copy)"
    assert second.name == "Cyber Security Concept (copy 2)"


def test_duplicate_with_explicit_name(template_service, profile_service):
    template = _template(template_service, profile_service)
    copy = template_service.duplicate_template(template.id, new_name="Networking Concept")
    assert copy.name == "Networking Concept"


def test_duplicate_missing_raises(template_service):
    with pytest.raises(TemplateNotFoundError):
        template_service.duplicate_template(999)


# --- create term from template --------------------------------------------


def test_apply_creates_term_with_sections(template_service, glossary_service, profile_service):
    template = _template(template_service, profile_service)
    template_service.add_section(template.id, "Definition")
    template_service.add_section(template.id, "Ports")

    term = template_service.create_term_from_template(template.id, "LDAP")

    assert term.term == "LDAP"
    assert term.profile_id == template.profile_id
    sections = glossary_service.list_sections(term.id)
    assert [s.title for s in sections] == ["Definition", "Ports"]
    assert all(s.content == "" for s in sections)


def test_apply_placeholder_is_not_copied_into_content(
    template_service, glossary_service, profile_service
):
    template = _template(template_service, profile_service)
    template_service.add_section(template.id, "Ports", placeholder="e.g. 389")
    term = template_service.create_term_from_template(template.id, "LDAP")
    section = glossary_service.list_sections(term.id)[0]
    assert section.title == "Ports"
    assert section.content == ""


def test_apply_with_no_sections_creates_empty_term(
    template_service, glossary_service, profile_service
):
    template = _template(template_service, profile_service)
    term = template_service.create_term_from_template(template.id, "LDAP")
    assert glossary_service.list_sections(term.id) == []


def test_apply_rejects_empty_term(template_service, profile_service):
    template = _template(template_service, profile_service)
    with pytest.raises(ValueError):
        template_service.create_term_from_template(template.id, "   ")


def test_apply_missing_template_raises(template_service):
    with pytest.raises(TemplateNotFoundError):
        template_service.create_term_from_template(999, "LDAP")


def test_apply_duplicate_term_name_raises(
    template_service, glossary_service, profile_service
):
    template = _template(template_service, profile_service)
    glossary_service.create_term(template.profile_id, "LDAP")
    with pytest.raises(DuplicateTermNameError):
        template_service.create_term_from_template(template.id, "LDAP")


def test_applied_sections_independent_from_template(
    template_service, glossary_service, profile_service
):
    template = _template(template_service, profile_service)
    template_service.add_section(template.id, "Definition")
    template_service.add_section(template.id, "Examples")

    term = template_service.create_term_from_template(template.id, "LDAP")

    sections = template_service.list_sections(template.id)
    template_service.set_section_title(sections[0].id, "Changed title")
    template_service.add_section(template.id, "New section")
    template_service.delete_section(sections[1].id)

    assert [s.title for s in glossary_service.list_sections(term.id)] == [
        "Definition",
        "Examples",
    ]
