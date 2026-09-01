"""Term list widget: compact, searchable, sortable list of terms with multi-select.

Two-line card rows (§15): leading hue tile, term name, optional category chip, full
name. The list has its own filter input, a sort dropdown, a bulk-selection bar, an empty
state, and a compact pinned "New term" primary action.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.database.repositories import DomainError
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.search_service import SearchService
from cyberglossary.ui.components import EmptyState
from cyberglossary.ui.dialog_utils import ConfirmDialog
from cyberglossary.ui.icons import filter_icon, plus, sort_icon
from cyberglossary.ui.list_utils import (
    TermListWidget,
    add_term_item,
    sync_multi_highlight,
    sync_selection_highlight,
)
from cyberglossary.ui.term_dialog import TermCreateDialog


class _TermListWidget(TermListWidget):
    delete_pressed = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete and self.selectedItems():
            self.delete_pressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_A and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.selectAll()
            event.accept()
            return
        super().keyPressEvent(event)


class TermList(QWidget):
    term_selected = Signal(object)  # term id (int) or None
    multi_selected = Signal(int)  # number of selected terms (>1)

    _SORT_MODES = ("Default", "A-Z", "Z-A", "Category")

    def __init__(
        self,
        glossary_service: GlossaryService,
        search_service: SearchService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._service = glossary_service
        self._search_service = search_service
        self._profile_id: int | None = None
        self._terms = []
        self._search_text = ""
        self._sort_mode = "Default"
        self._category_cache: dict[int, str | None] = {}
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._reload_list)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 0)
        layout.setSpacing(8)

        self.setMinimumWidth(260)
        self.setMaximumWidth(420)

        # Pane header: title + subtle count, filter/sort icon buttons.
        header = QHBoxLayout()
        title = QLabel("All Terms")
        title.setObjectName("listTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("countBadge")
        header.addWidget(title)
        header.addWidget(self.count_label)
        header.addStretch(1)

        self.filter_btn = QToolButton()
        self.filter_btn.setIcon(filter_icon())
        self.filter_btn.setToolTip("Filter terms (Ctrl+F)")
        self.filter_btn.clicked.connect(self._focus_filter)
        header.addWidget(self.filter_btn)

        self.sort_btn = QToolButton()
        self.sort_btn.setIcon(sort_icon())
        self.sort_btn.setToolTip("Sort terms")
        self.sort_btn.clicked.connect(self._open_sort_menu)
        header.addWidget(self.sort_btn)
        layout.addLayout(header)

        # Filter input.
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("filter")
        self.filter_edit.setPlaceholderText("Search terms\u2026")
        self.filter_edit.setFixedHeight(32)
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.addAction(filter_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.filter_edit)

        # Empty state (no terms at all, or no filter matches).
        self.empty_state = EmptyState(
            "No terms yet", "Use New term below to add your first term."
        )
        self.empty_state.action_btn.clicked.connect(self._clear_filter)
        layout.addWidget(self.empty_state, 1)
        self.empty_state.setVisible(False)

        # List.
        self.list = _TermListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._on_selection_changed)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.list.delete_pressed.connect(self._prompt_delete_selected)
        layout.addWidget(self.list, 1)

        # Multi-selection bulk bar.
        self.action_bar = QFrame()
        self.action_bar.setObjectName("selectionBar")
        bar_layout = QHBoxLayout(self.action_bar)
        bar_layout.setContentsMargins(10, 6, 10, 6)
        self.selection_label = QLabel("")
        self.selection_label.setObjectName("muted")
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.setObjectName("danger")
        self.delete_selected_btn.clicked.connect(self._prompt_delete_selected)
        bar_layout.addWidget(self.selection_label)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self.delete_selected_btn)
        self.action_bar.setVisible(False)
        layout.addWidget(self.action_bar)

        # Pinned bottom bar: compact app-wide primary "New term".
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("divider")
        bottom_wrap = QVBoxLayout()
        bottom_wrap.setContentsMargins(0, 0, 0, 0)
        bottom_wrap.setSpacing(0)
        bottom_wrap.addWidget(divider)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 10, 0, 10)
        bottom_row.setSpacing(0)
        self.new_btn = QPushButton("New term")
        self.new_btn.setObjectName("primary")
        self.new_btn.setIcon(plus())
        self.new_btn.setFixedHeight(36)
        self.new_btn.setToolTip("New term (Ctrl+N)")
        self.new_btn.clicked.connect(self._prompt_new)
        bottom_row.addWidget(self.new_btn, 1)
        bottom_wrap.addLayout(bottom_row)
        layout.addLayout(bottom_wrap)

    # --- profile / refresh ------------------------------------------------

    def set_profile(self, profile_id: int | None) -> None:
        self._profile_id = profile_id
        self._category_cache = {}
        self.refresh()

    def set_search_text(self, text: str) -> None:
        self._search_text = text
        self.filter_edit.blockSignals(True)
        self.filter_edit.setText(text)
        self.filter_edit.blockSignals(False)
        self._debounce.start()

    def _on_filter_changed(self, text: str) -> None:
        self._search_text = text
        self._debounce.start()

    def _focus_filter(self) -> None:
        self.filter_edit.setFocus()
        self.filter_edit.selectAll()

    def refresh(self) -> None:
        self._terms = (
            self._service.list_terms(self._profile_id)
            if self._profile_id is not None
            else []
        )
        self._category_cache = {}
        self._reload_list()
        self._on_selection_changed()

    def _category_name(self, term_id: int) -> str | None:
        if term_id not in self._category_cache:
            category = self._service.get_term_category(term_id)
            self._category_cache[term_id] = category.name if category else None
        return self._category_cache[term_id]

    def _sorted_terms(self):
        if self._sort_mode == "A-Z":
            return sorted(self._terms, key=lambda t: t.term.lower())
        if self._sort_mode == "Z-A":
            return sorted(self._terms, key=lambda t: t.term.lower(), reverse=True)
        if self._sort_mode == "Category":
            return sorted(self._terms, key=lambda t: (self._category_name(t.id) or "").lower())
        return self._terms

    def _reload_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        searching = bool(self._search_text.strip())
        if searching:
            for result in self._search_service.search(self._search_text, self._profile_id):
                add_term_item(
                    self.list,
                    result.term_id,
                    result.term,
                    result.full_name,
                    result.category,
                )
            if self.list.count() == 0:
                placeholder = QListWidgetItem("No matching terms found.")
                placeholder.setFlags(Qt.ItemFlags())
                self.list.addItem(placeholder)
        else:
            for term in self._sorted_terms():
                add_term_item(
                    self.list,
                    term.id,
                    term.term,
                    term.full_name,
                    self._category_name(term.id),
                )
        self.list.blockSignals(False)

        no_terms = not self._terms and not searching
        no_matches = searching and self.list.count() == 1 and (
            self.list.item(0).data(Qt.ItemDataRole.UserRole) is None
        )
        self.empty_state.setVisible(no_terms or no_matches)
        self.list.setVisible(not no_terms and not no_matches)
        if no_terms:
            self.empty_state.set_text(
                "No terms yet", "Use New term below to add your first term."
            )
        elif no_matches:
            query = self._search_text.strip()
            self.empty_state.set_text(
                f'No terms match "{query}"',
                "Try a different filter, or add a new term.",
                action="Clear filter",
            )
        if searching:
            self.count_label.setText(f"({self.list.count():,})")
        else:
            self.count_label.setText(f"({len(self._terms):,})")
        self.list.schedule_refresh()

    def _clear_filter(self) -> None:
        self.set_search_text("")
        self.filter_edit.setFocus()

    # --- selection --------------------------------------------------------

    def selected_term_ids(self) -> list[int]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.list.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole) is not None
        ]

    def selected_term_id(self) -> int | None:
        ids = self.selected_term_ids()
        return ids[0] if len(ids) == 1 else None

    def clear_selection(self) -> None:
        self.list.clearSelection()

    def select(self, term_id: int) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == term_id:
                self.list.clearSelection()
                item.setSelected(True)
                self.list.setCurrentItem(item)
                return
        self.term_selected.emit(None)

    def _on_selection_changed(self) -> None:
        ids = self.selected_term_ids()
        count = len(ids)
        sync_selection_highlight(self.list)
        sync_multi_highlight(self.list, count > 1)
        if count > 1:
            self.selection_label.setText(f"{count} terms selected")
            self.action_bar.setVisible(True)
            self.multi_selected.emit(count)
        else:
            self.action_bar.setVisible(False)
            self.term_selected.emit(ids[0] if count == 1 else None)

    # --- actions (safe to call directly) ----------------------------------

    def add_term(self, name: str, full_name: str = ""):
        if self._profile_id is None:
            return None
        term = self._service.create_term(self._profile_id, name.strip(), full_name)
        self.refresh()
        self.select(term.id)
        return term

    def _prompt_delete_selected(self) -> None:
        term_ids = self.selected_term_ids()
        if not term_ids:
            return
        self._confirm_delete_terms(term_ids)

    def _confirm_delete_terms(self, term_ids: list[int]) -> None:
        count = len(term_ids)
        if count == 1:
            term = self._service.get_term(term_ids[0])
            title = f'Delete "{term.term}"?' if term else "Delete term?"
            message = "This term will be permanently removed."
        else:
            title = f"Delete {count} terms?"
            message = "The selected terms will be permanently removed."
        dialog = ConfirmDialog(title, message, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.was_confirmed():
            self._service.delete_terms(term_ids)
            self.refresh()
            self.term_selected.emit(None)

    # --- sort -------------------------------------------------------------

    def _open_sort_menu(self) -> None:
        menu = QMenu(self)
        for mode in self._SORT_MODES:
            action = menu.addAction(mode)
            action.setCheckable(True)
            action.setChecked(mode == self._sort_mode)
        chosen = menu.exec(self.sort_btn.mapToGlobal(self.sort_btn.rect().bottomLeft()))
        if chosen is not None:
            self._sort_mode = chosen.text()
            self._reload_list()

    # --- context menu ------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        selected = self.selected_term_ids()

        clicked_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if clicked_id is not None and clicked_id not in selected:
            self.list.clearSelection()
            item.setSelected(True)
            selected = [clicked_id]

        if len(selected) > 1:
            menu = QMenu(self)
            header = menu.addAction(f"{len(selected)} terms selected")
            header.setEnabled(False)
            menu.addSeparator()
            delete_action = menu.addAction("Delete Selected")
            chosen = menu.exec(self.list.mapToGlobal(pos))
            if chosen == delete_action:
                self._confirm_delete_terms(selected)
            return

        if clicked_id is None:
            return
        term = self._service.get_term(clicked_id)
        if term is None:
            return

        menu = QMenu(self)
        header = menu.addAction(term.term)
        header.setEnabled(False)
        menu.addSeparator()
        open_action = menu.addAction("Open")
        edit_action = menu.addAction("Edit")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Term")

        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen in (open_action, edit_action):
            self.select(clicked_id)
        elif chosen == delete_action:
            self._confirm_delete_terms([clicked_id])

    def _duplicate(self, term_id: int) -> None:
        new_term = self._service.duplicate_term(term_id)
        self.refresh()
        self.select(new_term.id)

    def _prompt_new(self) -> None:
        if self._profile_id is None:
            return
        dialog = TermCreateDialog("", self._service.list_categories(self._profile_id), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        draft = dialog.draft()
        if draft is None:
            return
        try:
            term = self._service.create_term(self._profile_id, draft.term, draft.full_name)
            if draft.category_id is not None:
                self._service.set_term_category(term.id, draft.category_id)
            self.refresh()
            self.select(term.id)
        except (DomainError, ValueError) as exc:
            self._error(str(exc))

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "adudu", message)
