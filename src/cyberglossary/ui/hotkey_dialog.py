"""Hotkey capture + settings dialogs.

The capture dialog detects the actual key combination (never asks the user to type a
string) and rejects modifier-only combinations. The settings dialog wires capture to a
caller-provided ``on_apply(hotkey) -> bool`` callback.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.ui.dialog_utils import center_dialog
from cyberglossary.windows.hotkey import (
    DEFAULT_HOTKEY,
    Hotkey,
    format_hotkey,
    hotkey_from_qt_event,
    hotkey_from_qt_mouse,
)


class HotkeyCaptureDialog(QDialog):
    def __init__(self, current: Hotkey, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Set Global Lookup Hotkey")
        self._captured: Hotkey | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Press the key combination you want to use."))
        layout.addWidget(QLabel(f"Current: {format_hotkey(current)}"))
        self.new_label = QLabel("New: [Waiting for key combination...]")
        layout.addWidget(self.new_label)

        self.save_btn = QPushButton("Save")
        self.save_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Cancel")
        row = QHBoxLayout()
        row.addWidget(self.cancel_btn)
        row.addWidget(self.save_btn)
        layout.addLayout(row)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)

    def captured_hotkey(self) -> Hotkey | None:
        return self._captured

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog(self, self.parentWidget())

    def keyPressEvent(self, event) -> None:
        hotkey = hotkey_from_qt_event(event.key(), event.modifiers())
        if hotkey is not None and hotkey.is_valid():
            self._captured = hotkey
            self.new_label.setText(f"New: {format_hotkey(hotkey)}")
            self.save_btn.setEnabled(True)
        event.accept()

    def mousePressEvent(self, event) -> None:
        hotkey = hotkey_from_qt_mouse(event.button(), event.modifiers())
        if hotkey is not None and hotkey.is_valid():
            self._captured = hotkey
            self.new_label.setText(f"New: {format_hotkey(hotkey)}")
            self.save_btn.setEnabled(True)
        event.accept()


class HotkeySettingsDialog(QDialog):
    def __init__(
        self,
        current: Hotkey,
        on_apply: Callable[[Hotkey], bool],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Hotkey Settings")
        self._current = current
        self._on_apply = on_apply

        layout = QVBoxLayout(self)
        self.current_label = QLabel(f"Global Lookup Hotkey: {format_hotkey(current)}")
        layout.addWidget(self.current_label)

        row = QHBoxLayout()
        self.change_btn = QPushButton("Change")
        self.reset_btn = QPushButton("Reset to Default")
        self.close_btn = QPushButton("Close")
        row.addWidget(self.change_btn)
        row.addWidget(self.reset_btn)
        row.addWidget(self.close_btn)
        layout.addLayout(row)

        self.change_btn.clicked.connect(self._change)
        self.reset_btn.clicked.connect(self._reset)
        self.close_btn.clicked.connect(self.accept)

    def _change(self) -> None:
        dialog = HotkeyCaptureDialog(self._current, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            hotkey = dialog.captured_hotkey()
            if hotkey is not None:
                self._apply(hotkey)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_dialog(self, self.parentWidget())

    def _reset(self) -> None:
        self._apply(DEFAULT_HOTKEY)

    def _apply(self, hotkey: Hotkey) -> None:
        if self._on_apply(hotkey):
            self._current = hotkey
            self.current_label.setText(f"Global Lookup Hotkey: {format_hotkey(hotkey)}")
        else:
            QMessageBox.warning(
                self,
                "Hotkey",
                f"Could not register {format_hotkey(hotkey)}. "
                "This shortcut may already be in use by another application.",
            )
