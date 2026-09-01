"""Tests for the lookup popup (rendering, actions, positioning) and the add-term dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from cyberglossary.database.models import Category, Section
from cyberglossary.services.lookup_service import LookupResult
from cyberglossary.ui.popup import LookupPopup, clamp_popup_position
from cyberglossary.ui.term_dialog import TermCreateDialog


def _section(sid, term_id, title, content, sort_order):
    return Section(sid, term_id, title, content, sort_order, "now", "now")


def _found(**kwargs):
    values = {
        "term_id": 1,
        "term": "LDAP",
        "full_name": "",
        "category": None,
        "tags": [],
        "sections": [],
        "profile_name": "Cyber Security",
    }
    values.update(kwargs)
    return LookupResult(
        found=True,
        query=values["term"],
        term_id=values["term_id"],
        term=values["term"],
        full_name=values["full_name"],
        category=values["category"],
        tags=values["tags"],
        sections=values["sections"],
        profile_name=values["profile_name"],
    )


def _section_titles(popup):
    return [section.title for section in popup._sections]


# --- positioning -----------------------------------------------------------


def test_clamp_normal():
    assert clamp_popup_position(100, 100, 420, 300, (0, 0, 1920, 1080)) == (108, 108)


def test_clamp_right_edge():
    x, y = clamp_popup_position(1900, 100, 420, 300, (0, 0, 1920, 1080))
    assert x == 1900 - 420 - 8
    assert y == 108


def test_clamp_bottom_edge():
    x, y = clamp_popup_position(100, 1000, 420, 300, (0, 0, 1920, 1080))
    assert y == 1080 - 300 - 8
    assert x == 108


def test_clamp_negative_monitor():
    x, y = clamp_popup_position(-100, -100, 420, 300, (-1920, 0, 1920, 1080))
    assert x >= -1920
    assert y >= 0


# --- found popup -----------------------------------------------------------


def test_found_popup_renders_sections_dynamically(qapp):
    popup = LookupPopup()
    result = _found(
        sections=[
            _section(1, 1, "Ports", "389", 0),
            _section(2, 1, "Attack Techniques", "x", 1),
            _section(3, 1, "Detection", "y", 2),
        ]
    )
    popup.show_result(result)
    assert _section_titles(popup) == ["Ports", "Attack Techniques", "Detection"]


def test_popup_has_no_hard_coded_section_names(qapp):
    popup = LookupPopup()
    result = _found(sections=[_section(1, 1, "Ports", "", 0)])
    popup.show_result(result)
    assert "Definition" not in _section_titles(popup)
    assert "Examples" not in _section_titles(popup)


def test_popup_renders_empty_sections(qapp):
    popup = LookupPopup()
    popup.show_result(_found())
    assert _section_titles(popup) == []


def test_popup_renders_many_sections_in_order(qapp):
    popup = LookupPopup()
    sections = [_section(i, 1, f"Section {i}", "", i) for i in range(20)]
    popup.show_result(_found(sections=sections))
    assert _section_titles(popup) == [f"Section {i}" for i in range(20)]


def test_popup_renders_metadata(qapp):
    popup = LookupPopup()
    result = _found(
        full_name="Lightweight Directory Access Protocol",
        category="Active Directory",
    )
    popup.show_result(result)
    assert popup._title_label.text() == "LDAP"
    assert "Lightweight Directory Access Protocol" in popup._subtitle_label.text()
    assert popup._category_badge.text() == "Active Directory"
    assert not popup._category_badge.isHidden()


# --- actions ---------------------------------------------------------------


def test_open_full_page_action(qapp):
    popup = LookupPopup()
    popup.show_result(_found(term_id=42))
    emitted = []
    popup.open_requested.connect(emitted.append)
    popup.open_btn.click()
    assert emitted == [42]


def test_edit_action(qapp):
    popup = LookupPopup()
    popup.show_result(_found(term_id=42))
    emitted = []
    popup.edit_requested.connect(emitted.append)
    popup.edit_btn.click()
    assert emitted == [42]


def test_close_action_hides_and_emits(qapp):
    popup = LookupPopup()
    popup.show_result(_found())
    popup.show()
    emitted = []
    popup.closed.connect(lambda: emitted.append(True))
    popup.close_btn.click()
    assert not popup.isVisible()
    assert emitted == [True]


# --- unknown term ----------------------------------------------------------


def test_unknown_term_popup(qapp):
    popup = LookupPopup()
    popup.show_result(LookupResult.not_found("LDAP"))
    texts = [label.text() for label in popup._content.findChildren(QLabel)]
    assert "Term not found in current profile." in texts
    assert popup.add_btn is not None


def test_add_term_action_emits_query(qapp):
    popup = LookupPopup()
    popup.show_result(LookupResult.not_found("LDAP"))
    emitted = []
    popup.add_term_requested.connect(emitted.append)
    popup.add_btn.click()
    assert emitted == ["LDAP"]


# --- accordion sections ----------------------------------------------------


def test_sections_start_expanded(qapp):
    popup = LookupPopup()
    popup.show_result(_found(sections=[_section(1, 1, "Definition", "x", 0)]))
    section = popup._sections[0]
    assert section.is_expanded() is True
    assert not section.body.isHidden()


def test_click_header_collapses_and_expands(qapp):
    popup = LookupPopup()
    popup.show_result(_found(sections=[_section(1, 1, "Definition", "x", 0)]))
    section = popup._sections[0]

    section.header_btn.click()
    assert section.is_expanded() is False
    assert section.body.isHidden()

    section.header_btn.click()
    assert section.is_expanded() is True
    assert not section.body.isHidden()


def test_sections_have_independent_state(qapp):
    popup = LookupPopup()
    popup.show_result(
        _found(sections=[_section(1, 1, "A", "", 0), _section(2, 1, "B", "", 1)])
    )
    a, b = popup._sections
    a.header_btn.click()
    assert a.is_expanded() is False
    assert b.is_expanded() is True


def test_content_intact_after_toggle(qapp):
    popup = LookupPopup()
    popup.show_result(_found(sections=[_section(1, 1, "Definition", "The content", 0)]))
    section = popup._sections[0]
    section.header_btn.click()
    section.header_btn.click()
    assert section.body.text() == "The content"


def test_new_lookup_resets_expansion(qapp):
    popup = LookupPopup()
    popup.show_result(_found(sections=[_section(1, 1, "Definition", "x", 0)]))
    popup._sections[0].header_btn.click()
    assert popup._sections[0].is_expanded() is False

    popup.show_result(_found(term="Kerberos", sections=[_section(2, 1, "Ports", "389", 0)]))
    assert popup._sections[0].is_expanded() is True
    assert popup._sections[0].title == "Ports"


# --- add-term dialog -------------------------------------------------------


def test_term_create_dialog_draft(qapp):
    dialog = TermCreateDialog("LDAP", [Category(1, 1, "Active Directory", 0)])
    dialog.fullname_edit.setText("Lightweight Directory Access Protocol")
    dialog.category_combo.setCurrentIndex(1)
    draft = dialog.draft()
    assert draft.term == "LDAP"
    assert draft.full_name == "Lightweight Directory Access Protocol"
    assert draft.category_id == 1


def test_term_create_dialog_empty_term_returns_none(qapp):
    dialog = TermCreateDialog("", [])
    assert dialog.draft() is None


# --- pipeline integration (hotkey → capture → normalize → lookup → popup) ---


def test_pipeline_to_popup(profile_service, glossary_service, search_service, qapp):
    from cyberglossary.services.lookup_service import LookupService

    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
    glossary_service.add_section(term.id, "Ports", "389")

    service = LookupService(lambda: "LDAP", profile_service, glossary_service, search_service)
    popup = LookupPopup()

    popup.show_result(service.run())

    assert _section_titles(popup) == ["Ports"]
    assert popup._title_label.text() == "LDAP"
    assert "Lightweight Directory Access Protocol" in popup._subtitle_label.text()


# --- popup size / display --------------------------------------------------


def test_popup_has_minimum_size(qapp):
    popup = LookupPopup()
    assert popup.minimumSize().width() >= 320
    assert popup.minimumSize().height() >= 240


def test_popup_display_keeps_manual_size(qapp):
    popup = LookupPopup()
    popup.display(_found())
    assert popup.isVisible()
    width = popup.width()
    height = popup.height()

    popup.display(_found(term="Kerberos"))
    assert popup.isVisible()
    assert popup.width() == width
    assert popup.height() == height
