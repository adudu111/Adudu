"""Add-term dialog (opened from the lookup popup's "Add Term" action).

Collects term / full name / category and exposes a ``TermDraft``. It uses no repositories
directly — the caller performs creation through ``GlossaryService``.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from cyberglossary.database.models import Category
from cyberglossary.ui.dialog_utils import FramelessDialog


@dataclass
class TermDraft:
    term: str
    full_name: str = ""
    category_id: int | None = None


class TermCreateDialog(FramelessDialog):
    def __init__(
        self,
        term: str,
        categories: list[Category],
        parent: QWidget | None = None,
    ):
        super().__init__("New Term", parent, width=420)

        self.term_edit = QLineEdit(term)
        self.term_edit.setPlaceholderText("Term name")
        self.fullname_edit = QLineEdit()
        self.fullname_edit.setPlaceholderText("Full name (optional)")
        self.category_combo = QComboBox()
        self.category_combo.addItem("(none)", None)
        for category in categories:
            self.category_combo.addItem(category.name, category.id)

        form = QFormLayout()
        form.addRow("Term", self.term_edit)
        form.addRow("Full Name", self.fullname_edit)
        form.addRow("Category", self.category_combo)
        self.body_layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        self.footer_layout.addWidget(self.buttons)

    def _on_accept(self) -> None:
        if self.draft() is None:
            return
        self.accept()

    def draft(self) -> TermDraft | None:
        term = self.term_edit.text().strip()
        if not term:
            return None
        return TermDraft(
            term=term,
            full_name=self.fullname_edit.text().strip(),
            category_id=self.category_combo.currentData(),
        )
