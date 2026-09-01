"""Add-existing-terms dialog: assign terms from the current profile to a category."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from cyberglossary.ui.dialog_utils import FramelessDialog


@dataclass(frozen=True)
class TermOption:
    term_id: int
    term: str
    full_name: str
    current_category: str | None


class AddTermsDialog(FramelessDialog):
    def __init__(
        self,
        category_name: str,
        terms: list[TermOption],
        parent: QWidget | None = None,
    ):
        super().__init__(f"Add Terms to \"{category_name}\"", parent, width=520)
        self._category_name = category_name
        self._terms = terms
        self._all_items: list[QListWidgetItem] = []

        self.body_layout.addWidget(QLabel(f'Add terms to "{category_name}":'))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search terms\u2026")
        self.search_edit.textChanged.connect(self._filter)
        self.body_layout.addWidget(self.search_edit)

        self.term_list = QListWidget()
        self.body_layout.addWidget(self.term_list, 1)

        for option in terms:
            if option.current_category == category_name:
                item = QListWidgetItem(f"{option.term}   (already in {category_name})")
                item.setData(Qt.ItemDataRole.UserRole, option.term_id)
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                label = self._label(option)
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, option.term_id)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            self.term_list.addItem(item)
            self._all_items.append(item)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add Selected")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.footer_layout.addWidget(self.buttons)

    @staticmethod
    def _label(option: TermOption) -> str:
        base = option.term if not option.full_name else f"{option.term} \u2014 {option.full_name}"
        if option.current_category:
            return f"{base}   (in {option.current_category})"
        return base

    def _filter(self, text: str) -> None:
        needle = text.lower()
        for item in self._all_items:
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def selected_ids(self) -> list[int]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._all_items
            if item.checkState() == Qt.CheckState.Checked
        ]
