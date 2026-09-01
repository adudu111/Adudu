"""Settings dialog (DESIGN.md §21): theme, hotkey, clipboard capture, data actions.

Purely presentational — every control delegates to callbacks provided by the caller
(app.py), which drive the existing services unchanged.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cyberglossary.ui.components import Switch
from cyberglossary.ui.dialog_utils import FramelessDialog


class SettingsDialog(FramelessDialog):
    def __init__(
        self,
        dark: bool,
        hotkey_text: str,
        capture_on: bool,
        on_theme: Callable[[bool], None],
        on_change_hotkey: Callable[[], None],
        on_capture: Callable[[bool], None],
        on_file: Callable[[str], None],
        parent: QWidget | None = None,
    ):
        super().__init__("Settings", parent, width=520)
        self._on_file = on_file

        self.theme_switch = Switch(dark)
        self.theme_switch.toggled.connect(on_theme)
        self.body_layout.addWidget(self._row("Theme", "Dark is the primary visual reference. "
            "Both themes share one component system.", self.theme_switch))

        change_btn = QPushButton("Change")
        change_btn.setObjectName("ghost")
        change_btn.clicked.connect(on_change_hotkey)
        self.body_layout.addWidget(self._row("Global hotkey", f"Opens the lookup popup "
            f"from anywhere \u00b7  {hotkey_text}", change_btn))

        self.capture_switch = Switch(capture_on)
        self.capture_switch.toggled.connect(on_capture)
        self.body_layout.addWidget(self._row("Clipboard text capture", "Watched clipboard "
            "text opens the lookup popup for a quick definition.", self.capture_switch))

        fts_chip = QLabel("FTS5")
        fts_chip.setObjectName("kbdChip")
        self.body_layout.addWidget(self._row("Search engine", "Existing SearchService / "
            "FTS5 \u2014 matches term, full name and aliases.", fts_chip))

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        import_btn = QPushButton("Import JSON")
        import_btn.setObjectName("ghost")
        import_btn.setFixedHeight(28)
        import_btn.clicked.connect(lambda: self._on_file("import-json"))
        export_btn = QPushButton("Export JSON")
        export_btn.setObjectName("ghost")
        export_btn.setFixedHeight(28)
        export_btn.clicked.connect(lambda: self._on_file("export-json"))
        file_row.addWidget(import_btn)
        file_row.addWidget(export_btn)
        file_row.addStretch(1)
        self.body_layout.addWidget(self._row("Import / Export", "Canonical entry is the "
            "File menu; these call the same existing handlers.", file_row))

        backup_row = QHBoxLayout()
        backup_row.setSpacing(8)
        backup_btn = QPushButton("Backup Database")
        backup_btn.setObjectName("ghost")
        backup_btn.setFixedHeight(28)
        backup_btn.clicked.connect(lambda: self._on_file("backup"))
        restore_btn = QPushButton("Restore Database")
        restore_btn.setObjectName("ghost")
        restore_btn.setFixedHeight(28)
        restore_btn.clicked.connect(lambda: self._on_file("restore"))
        backup_row.addWidget(backup_btn)
        backup_row.addWidget(restore_btn)
        backup_row.addStretch(1)
        self.body_layout.addWidget(self._row("Backup / Restore", "Snapshot the active "
            "database via the File menu.", backup_row))

        done_btn = QPushButton("Done")
        done_btn.setObjectName("primary")
        done_btn.clicked.connect(self.accept)
        self.footer_layout.addWidget(done_btn)

    @staticmethod
    def _row(title: str, desc: str, control) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(16)
        column = QVBoxLayout()
        column.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        column.addWidget(title_label)
        desc_label = QLabel(desc)
        desc_label.setObjectName("muted")
        desc_label.setWordWrap(True)
        column.addWidget(desc_label)
        layout.addLayout(column, 1)
        if isinstance(control, QHBoxLayout):
            layout.addLayout(control)
        else:
            layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        return row