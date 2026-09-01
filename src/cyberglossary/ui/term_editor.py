"""Term detail workspace: a document-style reader with an explicit edit mode.

Renders the term as a knowledge page — large display title, secondary full name,
category chip, alias chips, and dynamic section accordion cards. Editing happens in a
dedicated edit mode (header form + inline section actions); the read view never shows
giant form inputs. Sections render dynamically from ``GlossaryService``; no section
title is hard-coded. Uses ``GlossaryService`` only — no direct SQLite access.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.database.repositories import DomainError
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.ui import theme
from cyberglossary.ui.components import AliasChip, CategoryChip, EmptyState, FlowLayout
from cyberglossary.ui.dialog_utils import ConfirmDialog, NameDialog
from cyberglossary.ui.icons import more_horizontal, pencil, plus
from cyberglossary.ui.section_editor import SectionEditor

_COLUMN_MAX_WIDTH = 860


class TermEditor(QWidget):
    term_deleted = Signal()
    term_duplicated = Signal(int)  # new term id
    term_renamed = Signal(int)  # term id

    def __init__(self, glossary_service: GlossaryService, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = glossary_service
        self._term_id: int | None = None
        self._term_name: str = ""
        self._mode = "empty"  # "empty" | "read" | "edit"
        self.sections: list[SectionEditor] = []
        self._build()
        self.set_term(None)

    # --- build -------------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.setMinimumWidth(480)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        centering = QHBoxLayout(content)
        centering.setContentsMargins(0, 0, 0, 0)
        centering.setSpacing(0)
        centering.addStretch(1)

        self._column = QWidget()
        self._column.setMaximumWidth(_COLUMN_MAX_WIDTH)
        centering.addWidget(self._column, 1)
        centering.addStretch(1)

        col = QVBoxLayout(self._column)
        col.setContentsMargins(24, 28, 24, 48)
        col.setSpacing(16)

        self.empty_state = EmptyState(
            "No term selected", "Select a term from the list to view its details."
        )
        col.addWidget(self.empty_state)

        self._read_header = self._build_read_header()
        col.addWidget(self._read_header)

        self._edit_header = self._build_edit_header()
        col.addWidget(self._edit_header)

        self._aliases_block = self._build_aliases_block()
        col.addWidget(self._aliases_block)

        self._sections_block = self._build_sections_block()
        col.addWidget(self._sections_block)

        self._details_footer = self._build_details_footer()
        col.addWidget(self._details_footer)

        self._edit_footer = self._build_edit_footer()
        col.addWidget(self._edit_footer)

        # Keep all blocks at their natural height; extra space goes to the bottom.
        col.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_read_header(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.title_label = QLabel("")
        self.title_label.setObjectName("termDisplayTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_row.addWidget(self.title_label, 1)

        self.overflow_btn = QToolButton()
        self.overflow_btn.setIcon(more_horizontal())
        self.overflow_btn.setToolTip("More actions")
        self.overflow_btn.clicked.connect(self._open_overflow_menu)
        title_row.addWidget(self.overflow_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("primary")
        self.edit_btn.setIcon(pencil())
        self.edit_btn.setToolTip("Edit this term (Ctrl+E)")
        self.edit_btn.clicked.connect(self.enter_edit_mode)
        title_row.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(title_row)

        self.subtitle_row = QHBoxLayout()
        self.subtitle_row.setSpacing(8)
        self.category_chip = CategoryChip("")
        self.category_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_chip.mousePressEvent = lambda _event: self.enter_edit_mode()
        self.subtitle_row.addWidget(self.category_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("termDisplaySubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.subtitle_row.addWidget(self.subtitle_label, 1)
        layout.addLayout(self.subtitle_row)
        return widget

    def _build_edit_header(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("termTitleEdit")
        self.name_edit.setPlaceholderText("Term")
        self.name_edit.editingFinished.connect(self._on_name_edited)
        layout.addWidget(self.name_edit)

        self.fullname_edit = QLineEdit()
        self.fullname_edit.setPlaceholderText("Full name (optional)")
        self.fullname_edit.editingFinished.connect(self._on_fullname_edited)
        layout.addWidget(self.fullname_edit)

        category_row = QHBoxLayout()
        category_row.setSpacing(8)
        category_label = QLabel("Category")
        category_label.setObjectName("muted")
        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        category_row.addWidget(category_label)
        category_row.addWidget(self.category_combo, 1)
        layout.addLayout(category_row)

        return widget

    def _build_aliases_block(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.aliases_label = QLabel("Aliases")
        self.aliases_label.setObjectName("aliasesLabel")
        layout.addWidget(self.aliases_label)

        self.aliases_container = QWidget()
        self.aliases_layout = FlowLayout(self.aliases_container, spacing=6)
        layout.addWidget(self.aliases_container)

        self.alias_input = QLineEdit()
        self.alias_input.setObjectName("filter")
        self.alias_input.setPlaceholderText("Add alias (Enter)")
        self.alias_input.setFixedHeight(32)
        self.alias_input.returnPressed.connect(self._on_alias_entered)
        layout.addWidget(self.alias_input)

        return widget

    def _on_alias_entered(self) -> None:
        alias = self.alias_input.text().strip()
        if not alias:
            return
        try:
            self.add_alias(alias)
            self.alias_input.clear()
        except (DomainError, ValueError) as exc:
            self._error(str(exc))

    def _build_sections_block(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(12)
        layout.addWidget(self.sections_container)

        self.add_section_btn = QPushButton("Add section")
        self.add_section_btn.setObjectName("addSectionBtn")
        self.add_section_btn.setIcon(plus())
        self.add_section_btn.setFixedHeight(36)
        self.add_section_btn.clicked.connect(self._prompt_add_section)
        layout.addWidget(self.add_section_btn)

        return widget

    def _build_details_footer(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("emptyWell")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        self.sections_footnote_label = QLabel("")
        self.sections_footnote_label.setObjectName("detailsFootnote")
        layout.addWidget(self.sections_footnote_label)
        layout.addStretch(1)
        self.category_footnote_label = QLabel("")
        self.category_footnote_label.setObjectName("detailsFootnoteCat")
        layout.addWidget(self.category_footnote_label)
        return widget

    def _build_edit_footer(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("ghost")
        self.cancel_btn.clicked.connect(self._leave_edit_mode)
        self.done_btn = QPushButton("Done")
        self.done_btn.setObjectName("primary")
        self.done_btn.clicked.connect(self._leave_edit_mode)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.done_btn)
        return widget

    # --- mode management ---------------------------------------------------

    def _apply_mode_visibility(self) -> None:
        is_empty = self._mode == "empty"
        is_read = self._mode == "read"
        is_edit = self._mode == "edit"

        self.empty_state.setVisible(is_empty)
        self._read_header.setVisible(is_read)
        self._edit_header.setVisible(is_edit)
        self._aliases_block.setVisible(not is_empty)
        self.alias_input.setVisible(is_edit)
        self.aliases_label.setVisible(not is_empty)
        self._sections_block.setVisible(not is_empty)
        self._details_footer.setVisible(is_read)
        self._edit_footer.setVisible(is_edit)

    def enter_edit_mode(self) -> None:
        if self._term_id is None:
            return
        self._mode = "edit"
        self._apply_mode_visibility()
        self._reload_aliases()
        self._reload_sections()
        self.name_edit.setFocus()

    def _leave_edit_mode(self) -> None:
        if self._term_id is None:
            return
        self._mode = "read"
        self._refresh_read_header()
        self._apply_mode_visibility()
        self._reload_aliases()
        self._reload_sections()

    # --- load / clear -----------------------------------------------------

    def show_multi_selection(self, count: int) -> None:
        """Show a neutral state when multiple terms are selected."""
        self.set_term(None)
        self.empty_state.set_text(f"{count} terms selected", "Select a single term to view its details.")

    def set_term(self, term_id: int | None) -> None:
        self._term_id = term_id
        self._term_name = ""
        if term_id is None:
            self._mode = "empty"
            self.empty_state.set_text(
                "Select a term to view it",
                "Use the list, or press Ctrl K to search.",
            )
            self._clear_widgets()
            self._apply_mode_visibility()
            self._set_enabled(False)
            return
        term = self._service.get_term(term_id)
        if term is None:
            self._mode = "empty"
            self._clear_widgets()
            self._apply_mode_visibility()
            self._set_enabled(False)
            return
        self._term_name = term.term
        self.name_edit.setText(term.term)
        self.fullname_edit.setText(term.full_name)
        self._reload_category(term)
        self._mode = "read"
        self._refresh_read_header()
        self._apply_mode_visibility()
        self._reload_aliases()
        self._reload_sections()
        self._set_enabled(True)

    def _clear_widgets(self) -> None:
        self.name_edit.clear()
        self.fullname_edit.clear()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.blockSignals(False)
        self._clear_aliases()
        self._clear_sections()

    def _refresh_read_header(self) -> None:
        if self._term_id is None:
            return
        term = self._service.get_term(self._term_id)
        if term is None:
            return
        self.title_label.setText(term.term)
        self.subtitle_label.setText(term.full_name)
        self.subtitle_label.setVisible(bool(term.full_name))
        category = self._service.get_term_category(term.id)
        if category is not None:
            self.category_chip.setText(category.name)
            hue = theme.category_hue(category.name)
            if hue is not None:
                self.category_chip.setProperty("hue", str(theme.CATEGORY_HUES.index(hue)))
                self.category_chip.style().unpolish(self.category_chip)
                self.category_chip.style().polish(self.category_chip)
            self.category_chip.setVisible(True)
        else:
            self.category_chip.setVisible(False)
        self._update_details_footer()

    def _update_details_footer(self) -> None:
        count = len(self.sections)
        noun = "section" if count == 1 else "sections"
        self.sections_footnote_label.setText(f"{count} {noun} \u00b7 dynamic titles")
        if self._term_id is None:
            self.category_footnote_label.setText("")
            return
        category = self._service.get_term_category(self._term_id)
        self.category_footnote_label.setText(category.name if category else "")
        self.category_footnote_label.setVisible(bool(category))

    def _reload_category(self, term) -> None:
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("(none)", None)
        for category in self._service.list_categories(term.profile_id):
            self.category_combo.addItem(category.name, category.id)
        current = self._service.get_term_category(term.id)
        if current is not None:
            index = self.category_combo.findData(current.id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        self.category_combo.blockSignals(False)

    def _on_category_changed(self) -> None:
        if self._term_id is None:
            return
        self._service.set_term_category(self._term_id, self.category_combo.currentData())

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (
            self.name_edit,
            self.fullname_edit,
            self.category_combo,
            self.edit_btn,
            self.overflow_btn,
            self.alias_input,
            self.add_section_btn,
        ):
            widget.setEnabled(enabled)

    # --- term metadata actions -------------------------------------------

    def rename(self, name: str):
        if self._term_id is None:
            return None
        name = name.strip()
        if not name:
            raise ValueError("Term name must not be empty.")
        updated = self._service.rename_term(self._term_id, name)
        self._term_name = updated.term
        self.title_label.setText(updated.term)
        self.term_renamed.emit(self._term_id)
        return updated

    def set_full_name(self, full_name: str):
        if self._term_id is None:
            return None
        updated = self._service.set_full_name(self._term_id, full_name)
        self.subtitle_label.setText(updated.full_name)
        self.subtitle_label.setVisible(bool(updated.full_name))
        return updated

    def duplicate_term(self):
        if self._term_id is None:
            return None
        new_term = self._service.duplicate_term(self._term_id)
        self.term_duplicated.emit(new_term.id)
        return new_term

    def delete_term(self) -> None:
        if self._term_id is None:
            return
        self._service.delete_term(self._term_id)
        self.term_deleted.emit()
        self.set_term(None)

    # --- alias actions ----------------------------------------------------

    def add_alias(self, alias: str):
        if self._term_id is None:
            return None
        result = self._service.add_alias(self._term_id, alias.strip())
        self._reload_aliases()
        return result

    def remove_alias(self, alias_id: int) -> None:
        self._service.delete_alias(alias_id)
        self._reload_aliases()

    def _clear_aliases(self) -> None:
        while self.aliases_layout.count():
            item = self.aliases_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _reload_aliases(self) -> None:
        self._clear_aliases()
        if self._term_id is None:
            return
        editable = self._mode == "edit"
        for alias in self._service.list_aliases(self._term_id):
            chip = AliasChip(alias.alias, removable=editable)
            if editable:
                chip.remove_requested.connect(lambda alias_id=alias.id: self.remove_alias(alias_id))
            self.aliases_layout.addWidget(chip)

    # --- section actions --------------------------------------------------

    def add_section(self, title: str, content: str = ""):
        if self._term_id is None:
            return None
        title = title.strip()
        if not title:
            raise ValueError("Section title must not be empty.")
        section = self._service.add_section(self._term_id, title, content)
        self._reload_sections()
        return section

    def delete_section(self, section_id: int) -> None:
        self._service.delete_section(section_id)
        self._reload_sections()

    def move_section(self, section_id: int, delta: int) -> None:
        if self._term_id is None:
            return
        ids = [s.section_id for s in self.sections]
        try:
            index = ids.index(section_id)
        except ValueError:
            return
        new_index = index + delta
        if new_index < 0 or new_index >= len(ids):
            return
        ids[index], ids[new_index] = ids[new_index], ids[index]
        self._service.reorder_sections(self._term_id, ids)
        self._reload_sections()

    def _clear_sections(self) -> None:
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.sections = []

    def _reload_sections(self) -> None:
        self._clear_sections()
        if self._term_id is None:
            self._update_details_footer()
            return
        read_only = self._mode != "edit"
        for index, section in enumerate(self._service.list_sections(self._term_id)):
            editor = SectionEditor(section.id, section.title, section.content, expanded=(index == 0))
            editor.set_read_only(read_only)
            editor.title_changed.connect(self._on_section_title_changed)
            editor.content_changed.connect(self._on_section_content_changed)
            editor.delete_requested.connect(self._on_section_delete_requested)
            editor.move_requested.connect(self.move_section)
            self.sections_layout.addWidget(editor)
            self.sections.append(editor)
        self._update_details_footer()

    # --- section signal handlers -----------------------------------------

    def _on_section_title_changed(self, section_id: int, title: str) -> None:
        title = title.strip()
        if not title:
            self._reload_sections()
            return
        try:
            self._service.rename_section(section_id, title)
        except (DomainError, ValueError) as exc:
            self._error(str(exc))
            self._reload_sections()

    def _on_section_content_changed(self, section_id: int, content: str) -> None:
        self._service.set_section_content(section_id, content)

    def _on_section_delete_requested(self, section_id: int) -> None:
        dialog = ConfirmDialog("Delete section?", "The section will be removed.", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.was_confirmed():
            self.delete_section(section_id)

    # --- term field handlers ---------------------------------------------

    def _on_name_edited(self) -> None:
        if self._term_id is None:
            return
        try:
            self.rename(self.name_edit.text())
        except (DomainError, ValueError) as exc:
            self.name_edit.setText(self._term_name)
            self._error(str(exc))

    def _on_fullname_edited(self) -> None:
        if self._term_id is None:
            return
        self.set_full_name(self.fullname_edit.text())

    def _open_overflow_menu(self) -> None:
        menu = QMenu(self)
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.overflow_btn.mapToGlobal(self.overflow_btn.rect().bottomLeft()))
        if chosen == duplicate_action:
            self._prompt_duplicate()
        elif chosen == delete_action:
            self._prompt_delete()

    # --- modal prompts ----------------------------------------------------

    def _prompt_add_section(self) -> None:
        dialog = NameDialog("New Section", "Section title", confirm_text="Create", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.add_section(dialog.value())
            except (DomainError, ValueError) as exc:
                self._error(str(exc))

    def _prompt_duplicate(self) -> None:
        try:
            self.duplicate_term()
        except (DomainError, ValueError) as exc:
            self._error(str(exc))

    def _prompt_delete(self) -> None:
        dialog = ConfirmDialog(
            "Delete term?",
            f'"{self._term_name}" will be permanently removed.',
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.was_confirmed():
            self.delete_term()

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "adudu", message)
