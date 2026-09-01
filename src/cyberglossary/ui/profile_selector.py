"""Profile selector widget (create / rename / delete / switch active profile).

Uses ``ProfileService`` only; never touches SQLite directly. Modal prompts are isolated
in the button handlers; the action methods below are safe to call directly (tests).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.database.repositories import DomainError
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.ui.dialog_utils import ConfirmDialog, NameDialog
from cyberglossary.ui.icons import more_horizontal, user_icon


class ProfileSelector(QWidget):
    profile_selected = Signal(object)  # profile id (int) or None

    def __init__(self, profile_service: ProfileService, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = profile_service
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(4)
        person = QLabel()
        person.setObjectName("muted")
        person.setPixmap(user_icon().pixmap(16, 16))
        row.addWidget(person)

        self.combo = QComboBox()
        self.combo.setObjectName("profileCombo")
        self.combo.currentIndexChanged.connect(self._on_activated)
        row.addWidget(self.combo, 1)

        self.overflow_btn = QToolButton()
        self.overflow_btn.setIcon(more_horizontal())
        self.overflow_btn.setToolTip("Rename / delete profile")
        self.overflow_btn.clicked.connect(self._open_overflow)
        row.addWidget(self.overflow_btn)
        layout.addLayout(row)

        self.new_btn = QPushButton("+ New profile")
        self.new_btn.setObjectName("ghost")
        self.new_btn.setFixedHeight(28)
        self.new_btn.clicked.connect(self._prompt_new)
        layout.addWidget(self.new_btn, 0, Qt.AlignmentFlag.AlignLeft)

    def _open_overflow(self) -> None:
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.overflow_btn.mapToGlobal(self.overflow_btn.rect().bottomLeft()))
        if chosen == rename_action:
            self._prompt_rename()
        elif chosen == delete_action:
            self._prompt_delete()

    # --- refresh / selection ---------------------------------------------

    def refresh(self) -> None:
        profiles = self._service.list_profiles()
        active_id = self._service.get_active_profile_id()
        self.combo.blockSignals(True)
        self.combo.clear()
        for profile in profiles:
            self.combo.addItem(profile.name, profile.id)
        if active_id is not None:
            index = self.combo.findData(active_id)
            if index >= 0:
                self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)

    def current_profile_id(self) -> int | None:
        index = self.combo.currentIndex()
        if index < 0:
            return None
        return self.combo.itemData(index)

    def select_profile(self, profile_id: int) -> None:
        self._service.set_active_profile(profile_id)
        self.refresh()
        self.profile_selected.emit(profile_id)

    def _on_activated(self, index: int) -> None:
        if index < 0:
            return
        profile_id = self.combo.itemData(index)
        if profile_id is not None:
            self._service.set_active_profile(profile_id)
            self.profile_selected.emit(profile_id)

    # --- actions (safe to call directly) ----------------------------------

    def create_profile(self, name: str):
        name = name.strip()
        if not name:
            return None
        profile = self._service.create_profile(name)
        self._service.set_active_profile(profile.id)
        self.refresh()
        self.profile_selected.emit(profile.id)
        return profile

    def rename_current(self, name: str):
        profile_id = self.current_profile_id()
        if profile_id is None:
            return None
        profile = self._service.rename_profile(profile_id, name.strip())
        self.refresh()
        return profile

    def delete_current(self) -> None:
        profile_id = self.current_profile_id()
        if profile_id is None:
            return
        self._service.delete_profile(profile_id)
        self.refresh()
        self.profile_selected.emit(self._service.get_active_profile_id())

    # --- modal prompts ----------------------------------------------------

    def _prompt_new(self) -> None:
        dialog = NameDialog("New Profile", "Profile name", confirm_text="Create", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.create_profile(dialog.value())
            except (DomainError, ValueError) as exc:
                self._error(str(exc))

    def _prompt_rename(self) -> None:
        profile_id = self.current_profile_id()
        if profile_id is None:
            return
        dialog = NameDialog(
            "Rename Profile", "New name", prefill=self._service.get_active_profile().name,
            confirm_text="Save", parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.rename_current(dialog.value())
            except (DomainError, ValueError) as exc:
                self._error(str(exc))

    def _prompt_delete(self) -> None:
        profile_id = self.current_profile_id()
        if profile_id is None:
            return
        dialog = ConfirmDialog(
            "Delete profile?",
            "The profile and all of its terms will be permanently removed.",
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.was_confirmed():
            try:
                self.delete_current()
            except (DomainError, ValueError) as exc:
                self._error(str(exc))

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "adudu", message)
