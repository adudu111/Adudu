"""Categories page: two-pane layout (Categories | Terms) per DESIGN.md §19.

Left: category rows (folder icon, name, count) + "All terms" row + New category action.
Right: the terms of the selected category (or all terms), with its own filter and count.
No middle details column. Category/term actions live in right-click context menus.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.database.repositories import DomainError
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.ui.add_terms_dialog import AddTermsDialog, TermOption
from cyberglossary.ui.dialog_utils import ConfirmDialog, NameDialog
from cyberglossary.ui.icons import (
    book_icon,
    chevron_down,
    chevron_up,
    filter_icon,
    folder_icon,
    plus,
    sort_icon,
)
from cyberglossary.ui.list_utils import (
    TermListWidget,
    add_term_item,
    sync_multi_highlight,
    sync_selection_highlight,
)


class CategoriesPage(QWidget):
    term_selected = Signal(int)  # term id (navigate to the term in the main editor)

    def __init__(
        self,
        glossary_service: GlossaryService,
        profile_service: ProfileService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._service = glossary_service
        self._profiles = profile_service
        self._search_text = ""
        self._term_filter_text = ""
        self._categories = []
        self._selected_category_id: int | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([280, 1100])
        layout.addWidget(splitter)

    def _build_left(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Categories")
        title.setObjectName("listTitle")
        self.cat_count_label = QLabel("")
        self.cat_count_label.setObjectName("countBadge")
        header.addWidget(title)
        header.addWidget(self.cat_count_label)
        header.addStretch(1)
        self.new_btn = QPushButton("New category")
        self.new_btn.setObjectName("ghost")
        self.new_btn.setIcon(plus())
        self.new_btn.setFixedHeight(28)
        self.new_btn.clicked.connect(self._on_add_category)
        header.addWidget(self.new_btn)
        layout.addLayout(header)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("filter")
        self.search_edit.setPlaceholderText("Search categories\u2026")
        self.search_edit.setFixedHeight(32)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        self.category_list = TermListWidget()
        self.category_list.currentItemChanged.connect(self._on_category_changed)
        self.category_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.category_list.customContextMenuRequested.connect(self._on_category_context_menu)
        layout.addWidget(self.category_list, 1)

        reorder = QHBoxLayout()
        reorder.setSpacing(4)
        self.up_btn = QToolButton()
        self.up_btn.setIcon(chevron_up())
        self.up_btn.setToolTip("Move category up")
        self.up_btn.clicked.connect(self._on_move_up)
        self.down_btn = QToolButton()
        self.down_btn.setIcon(chevron_down())
        self.down_btn.setToolTip("Move category down")
        self.down_btn.clicked.connect(self._on_move_down)
        reorder.addWidget(self.up_btn)
        reorder.addWidget(self.down_btn)
        reorder.addStretch(1)
        layout.addLayout(reorder)

        return panel

    def _build_right(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.category_name = QLabel("All terms")
        self.category_name.setObjectName("listTitle")
        self.category_name.setWordWrap(True)
        self.count_label = QLabel("")
        self.count_label.setObjectName("countBadge")
        header.addWidget(self.category_name)
        header.addWidget(self.count_label)
        header.addStretch(1)
        self.filter_btn = QToolButton()
        self.filter_btn.setIcon(filter_icon())
        self.filter_btn.setToolTip("Filter terms")
        self.filter_btn.clicked.connect(lambda: self.term_filter_edit.setFocus())
        header.addWidget(self.filter_btn)
        self.sort_btn = QToolButton()
        self.sort_btn.setIcon(sort_icon())
        self.sort_btn.setToolTip("Sort terms")
        header.addWidget(self.sort_btn)
        layout.addLayout(header)

        self.term_filter_edit = QLineEdit()
        self.term_filter_edit.setObjectName("filter")
        self.term_filter_edit.setPlaceholderText("Filter terms\u2026")
        self.term_filter_edit.setFixedHeight(32)
        self.term_filter_edit.textChanged.connect(self._on_term_filter_changed)
        layout.addWidget(self.term_filter_edit)

        self.term_list = TermListWidget()
        self.term_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.term_list.itemSelectionChanged.connect(self._on_term_selection_changed)
        self.term_list.itemDoubleClicked.connect(self._on_term_activated)
        self.term_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.term_list.customContextMenuRequested.connect(self._on_term_context_menu)
        layout.addWidget(self.term_list, 1)

        self.add_existing_btn = QPushButton("+ Add Existing Term")
        self.add_existing_btn.setObjectName("ghost")
        self.add_existing_btn.setFixedHeight(32)
        self.add_existing_btn.clicked.connect(self._on_add_existing)
        layout.addWidget(self.add_existing_btn)

        return panel

    # --- reload / state ----------------------------------------------------

    def reload(self) -> None:
        pid = self._profiles.get_active_profile_id()
        self._categories = self._service.list_categories(pid) if pid is not None else []
        self._reload_category_list()
        self._reload_right()

    def _reload_category_list(self) -> None:
        pid = self._profiles.get_active_profile_id()
        self.category_list.blockSignals(True)
        self.category_list.clear()
        needle = self._search_text.lower()
        for category in self._categories:
            if needle and needle not in category.name.lower():
                continue
            count = self._service.count_terms_by_category(category.id)
            add_term_item(
                self.category_list,
                category.id,
                category.name,
                f"{count} terms",
                tile_icon=folder_icon(),
            )
            if category.id == self._selected_category_id:
                self.category_list.setCurrentRow(self.category_list.count() - 1)
        # "All terms" row (deselect → all terms).
        total = len(self._service.list_terms(pid)) if pid is not None else 0
        add_term_item(
            self.category_list,
            None,
            "All terms",
            f"{total} terms",
            tile_icon=book_icon(),
        )
        if self._selected_category_id is None and self.category_list.count():
            self.category_list.setCurrentRow(self.category_list.count() - 1)
        self.category_list.blockSignals(False)
        self.cat_count_label.setText(f"({len(self._categories)})")
        self.category_list.schedule_refresh()

    def _reload_right(self) -> None:
        pid = self._profiles.get_active_profile_id()
        category = self._find_category(self._selected_category_id) if self._selected_category_id else None
        self.term_list.clear()
        if category is None:
            self.category_name.setText("All terms")
            self.add_existing_btn.setEnabled(False)
            terms = self._service.list_terms(pid) if pid is not None else []
        else:
            self.add_existing_btn.setEnabled(True)
            self.category_name.setText(category.name)
            terms = self._service.list_terms_by_category(category.id)
        needle = self._term_filter_text.lower()
        if needle:
            terms = [
                t for t in terms
                if needle in t.term.lower() or needle in t.full_name.lower()
            ]
        if category is not None:
            total = self._service.count_terms_by_category(category.id)
            self.count_label.setText(f"({len(terms)} of {total})")
        else:
            self.count_label.setText(f"({len(terms)})")
        for term in terms:
            add_term_item(self.term_list, term.id, term.term, term.full_name, category.name if category else None)
        sync_selection_highlight(self.term_list)
        sync_multi_highlight(self.term_list, False)
        self.term_list.schedule_refresh()

    def _find_category(self, category_id: int):
        for category in self._categories:
            if category.id == category_id:
                return category
        return None

    def _require_pid(self) -> int:
        pid = self._profiles.get_active_profile_id()
        if pid is None:
            raise ValueError("No active profile selected.")
        return pid

    # --- signal handlers ---------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._reload_category_list()

    def _on_term_filter_changed(self, text: str) -> None:
        self._term_filter_text = text
        self._reload_right()

    def _on_category_changed(self, current: QListWidgetItem | None, _previous=None) -> None:
        self._selected_category_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        sync_selection_highlight(self.category_list)
        self._reload_right()

    def _on_term_selection_changed(self) -> None:
        sync_selection_highlight(self.term_list)
        sync_multi_highlight(self.term_list, len(self.term_list.selectedItems()) > 1)

    def _on_term_activated(self, item: QListWidgetItem) -> None:
        self.term_selected.emit(item.data(Qt.ItemDataRole.UserRole))

    def _on_category_context_menu(self, pos) -> None:
        item = self.category_list.itemAt(pos)
        if item is None:
            return
        category_id = item.data(Qt.ItemDataRole.UserRole)
        category = self._find_category(category_id)
        if category is None:
            return

        menu = QMenu(self)
        header = menu.addAction(category.name)
        header.setEnabled(False)
        menu.addSeparator()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        chosen = menu.exec(self.category_list.mapToGlobal(pos))
        if chosen == rename_action:
            self._rename_category(category)
        elif chosen == delete_action:
            self._delete_category(category)

    def _on_term_context_menu(self, pos) -> None:
        item = self.term_list.itemAt(pos)
        if item is None:
            return
        term_id = item.data(Qt.ItemDataRole.UserRole)
        term = self._service.get_term(term_id)
        if term is None:
            return

        menu = QMenu(self)
        header = menu.addAction(term.term)
        header.setEnabled(False)
        menu.addSeparator()
        open_action = menu.addAction("Open")
        edit_action = menu.addAction("Edit")
        remove_action = menu.addAction("Remove from Category")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")

        chosen = menu.exec(self.term_list.mapToGlobal(pos))
        if chosen in (open_action, edit_action):
            self.term_selected.emit(term_id)
        elif chosen == remove_action:
            self._service.set_term_category(term_id, None)
            self.reload()
        elif chosen == delete_action:
            self._confirm_delete_term(term_id)

    # --- category actions --------------------------------------------------

    def _on_add_category(self) -> None:
        dialog = NameDialog("New Category", "Category name", confirm_text="Create", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            category = self._service.create_category(self._require_pid(), dialog.value())
            self._selected_category_id = category.id
            self.reload()
        except (DomainError, ValueError) as exc:
            self._error(str(exc))

    def _rename_category(self, category) -> None:
        dialog = NameDialog(
            "Rename Category", "Name", prefill=category.name, confirm_text="Save", parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._service.rename_category(category.id, dialog.value())
            self.reload()
        except (DomainError, ValueError) as exc:
            self._error(str(exc))

    def _delete_category(self, category) -> None:
        dialog = ConfirmDialog(
            f'Delete category "{category.name}"?',
            "Its terms will be kept \u2014 only the category assignment is cleared.",
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.was_confirmed():
            self._service.delete_category(category.id)
            self._selected_category_id = None
            self.reload()

    def _on_move_up(self) -> None:
        self._move(-1)

    def _on_move_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        ids = [c.id for c in self._categories]
        try:
            index = ids.index(self._selected_category_id)
        except ValueError:
            return
        new_index = index + delta
        if new_index < 0 or new_index >= len(ids):
            return
        ids[index], ids[new_index] = ids[new_index], ids[index]
        self._service.reorder_categories(self._require_pid(), ids)
        self.reload()

    # --- add-existing-term flow -------------------------------------------

    def _on_add_existing(self) -> None:
        category = self._find_category(self._selected_category_id) if self._selected_category_id else None
        if category is None:
            return
        options = []
        for term in self._service.list_terms(self._require_pid()):
            current = self._service.get_term_category(term.id)
            options.append(
                TermOption(term.id, term.term, term.full_name, current.name if current else None)
            )
        dialog = AddTermsDialog(category.name, options, self)
        if dialog.exec() != AddTermsDialog.DialogCode.Accepted:
            return
        self._assign_terms(category, dialog.selected_ids())

    def _assign_terms(self, category, term_ids: list[int]) -> None:
        to_move: list[tuple[int, str]] = []
        to_assign: list[int] = []
        for term_id in term_ids:
            current = self._service.get_term_category(term_id)
            if current is None:
                to_assign.append(term_id)
            elif current.id != category.id:
                to_move.append((term_id, current.name))

        if to_move:
            lines = [f"{self._service.get_term(tid).term} \u2192 {name}" for tid, name in to_move]
            message = (
                "The following terms are already assigned to another category:\n"
                + "\n".join(lines)
                + f'\n\nMove them to "{category.name}"?'
            )
            box = QMessageBox(self)
            box.setWindowTitle("Move Terms")
            box.setText(message)
            box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            move_btn = box.addButton("Move", QMessageBox.ButtonRole.AcceptRole)
            box.exec()
            if box.clickedButton() == move_btn:
                to_assign += [tid for tid, _ in to_move]

        for term_id in to_assign:
            self._service.set_term_category(term_id, category.id)
        self.reload()

    # --- term deletion -----------------------------------------------------

    def _confirm_delete_term(self, term_id: int) -> None:
        term = self._service.get_term(term_id)
        if term is None:
            return
        dialog = ConfirmDialog(
            f'Delete "{term.term}"?',
            "This term will be permanently removed.",
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.was_confirmed():
            self._service.delete_term(term_id)
            self.reload()

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "adudu", message)
