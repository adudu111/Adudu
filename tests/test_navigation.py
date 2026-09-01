"""Tests for the redesigned Library navigation and Categories page."""

from __future__ import annotations


def test_nav_buttons_exist(window):
    assert window.terms_btn.text() == "Terms"
    assert window.categories_btn.text() == "Categories"
    assert window.settings_btn.text() == "Settings"
    # Templates and Tags are removed from the product.
    assert not hasattr(window, "templates_btn")
    assert not hasattr(window, "tags_btn")
    assert not hasattr(window, "dashboard_btn")
    # Terms is the default view.
    assert window.stack.currentWidget() == window.terms_pane


def test_navigation_switches_views(window):
    window.categories_btn.click()
    assert window.stack.currentWidget() is window.categories_page
    window.terms_btn.click()
    assert window.stack.currentWidget() is window.terms_pane


def test_search_moves_to_header(window):
    assert hasattr(window, "search_edit")
    # The header search drives the term list and switches to the Terms view.
    window.categories_btn.click()
    window.search_edit.setText("ldap")
    assert window.stack.currentWidget() is window.terms_pane


def test_categories_navigation_and_reload(window, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "Active Directory")
    term = glossary_service.create_term(pid, "LDAP", "LDAP Protocol")
    glossary_service.set_term_category(term.id, category.id)

    window.categories_btn.click()

    assert window.stack.currentWidget() is window.categories_page
    cat_item = window.categories_page.category_list.itemWidget(
        window.categories_page.category_list.item(0)
    )
    assert cat_item.title.text() == "Active Directory"
    assert cat_item.subtitle.text() == "1 terms"
    term_item = window.categories_page.term_list.itemWidget(
        window.categories_page.term_list.item(0)
    )
    assert term_item.title.text() == "LDAP"
    assert term_item.subtitle.text() == "LDAP Protocol"


def test_term_editor_category_assignment(window, profile_service, glossary_service):
    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "Active Directory")
    term = glossary_service.create_term(pid, "LDAP")

    window.term_list.set_profile(pid)
    window.term_editor.set_term(term.id)

    index = window.term_editor.category_combo.findData(category.id)
    window.term_editor.category_combo.setCurrentIndex(index)
    assert glossary_service.get_term_category(term.id).name == "Active Directory"

    # Clear the category.
    window.term_editor.category_combo.setCurrentIndex(0)
    assert glossary_service.get_term_category(term.id) is None


def test_settings_emits_signal(window):
    emitted = []
    window.settings_requested.connect(lambda: emitted.append(True))
    window.settings_btn.click()
    assert emitted == [True]


def test_term_list_center_term_editor_right(window):
    editor_index = window.terms_split.indexOf(window.term_editor)
    list_index = window.terms_split.indexOf(window.term_list)
    assert editor_index >= 0 and list_index >= 0
    assert list_index < editor_index


def test_categories_page_assigns_existing_term(window, profile_service, glossary_service):
    from cyberglossary.database.models import Category

    pid = profile_service.create_profile("Cyber Security").id
    category = glossary_service.create_category(pid, "CRTO")
    term = glossary_service.create_term(pid, "LDAP")

    page = window.categories_page
    page._selected_category_id = category.id
    page._assign_terms(Category(category.id, pid, "CRTO", 0), [term.id])

    assert glossary_service.get_term_category(term.id).name == "CRTO"
    assert [t.term for t in glossary_service.list_terms(pid)] == ["LDAP"]


def test_add_terms_dialog_selection(qapp):
    from PySide6.QtCore import Qt

    from cyberglossary.ui.add_terms_dialog import AddTermsDialog, TermOption

    options = [
        TermOption(1, "LDAP", "LDAP Protocol", "Active Directory"),
        TermOption(2, "Kerberos", "", None),
        TermOption(3, "WMI", "", "CRTO"),  # already in the target category
    ]
    dialog = AddTermsDialog("CRTO", options)

    # "WMI" is already in CRTO -> disabled (not checkable).
    assert not (dialog.term_list.item(2).flags() & Qt.ItemFlag.ItemIsUserCheckable)

    dialog.term_list.item(0).setCheckState(Qt.CheckState.Checked)
    dialog.term_list.item(1).setCheckState(Qt.CheckState.Checked)
    assert set(dialog.selected_ids()) == {1, 2}


def test_term_list_duplicate_action(profile_service, glossary_service, search_service, qapp):
    from cyberglossary.ui.term_list import TermList

    pid = profile_service.create_profile("Cyber Security").id
    term = glossary_service.create_term(pid, "LDAP")

    term_list = TermList(glossary_service, search_service)
    term_list.set_profile(pid)
    term_list._duplicate(term.id)

    assert [t.term for t in glossary_service.list_terms(pid)] == ["LDAP", "LDAP (copy)"]
