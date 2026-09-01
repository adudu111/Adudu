"""A single collapsible section accordion card (DESIGN.md §18).

Binds to one section id and emits signals that the parent maps to ``GlossaryService``
calls. Section titles are completely dynamic — this widget hard-codes nothing. The
header carries a leading chevron, the dynamic title, hover-revealed edit actions
(reorder / rename / delete), and a trailing content-count badge. The first section opens
by default; others start collapsed.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.ui.icons import (
    chevron_down,
    chevron_up,
    chevrons_up_down,
    pencil,
    trash_icon,
)

_MAX_BODY_HEIGHT = 400


class _HeaderBar(QWidget):
    """Clickable header strip; clicks on empty areas toggle the section."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class SectionEditor(QWidget):
    title_changed = Signal(int, str)
    content_changed = Signal(int, str)
    delete_requested = Signal(int)
    move_requested = Signal(int, int)  # (section_id, delta)

    def __init__(
        self,
        section_id: int,
        title: str,
        content: str,
        expanded: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.section_id = section_id
        self._title = title
        self._suppress = False
        self._expanded = expanded
        self._read_only = True
        self._build()
        self.title_edit.setText(title)
        self.set_content(content)
        self.set_read_only(True)
        self._apply_expansion()

    def _build(self) -> None:
        self.setObjectName("sectionCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 10)
        outer.setSpacing(4)

        self.header = _HeaderBar()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 4, 0, 4)
        header_layout.setSpacing(6)

        self.collapse_btn = QToolButton()
        self.collapse_btn.setIcon(chevron_down())
        self.collapse_btn.setToolTip("Collapse / expand")
        self.collapse_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self.collapse_btn)

        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(self.title_label, 1)

        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("sectionTitleEdit")
        self.title_edit.setPlaceholderText("Section title")
        self.title_edit.editingFinished.connect(self._on_title_edited)
        header_layout.addWidget(self.title_edit, 1)

        self.reorder_btn = QToolButton()
        self.reorder_btn.setIcon(chevrons_up_down())
        self.reorder_btn.setToolTip("Reorder section")
        self.reorder_btn.clicked.connect(self._open_reorder_menu)
        header_layout.addWidget(self.reorder_btn)

        self.rename_btn = QToolButton()
        self.rename_btn.setIcon(pencil())
        self.rename_btn.setToolTip("Rename section")
        self.rename_btn.clicked.connect(self._start_rename)
        header_layout.addWidget(self.rename_btn)

        self.delete_btn = QToolButton()
        self.delete_btn.setIcon(trash_icon())
        self.delete_btn.setToolTip("Delete section")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.section_id))
        header_layout.addWidget(self.delete_btn)

        self.count_badge = QLabel("")
        self.count_badge.setObjectName("countBadge")
        header_layout.addWidget(self.count_badge)

        self.header.clicked.connect(self._toggle)
        outer.addWidget(self.header)

        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("Section content")
        self.content_edit.setMinimumHeight(0)
        self.content_edit.setMaximumHeight(_MAX_BODY_HEIGHT)
        self.content_edit.textChanged.connect(self._on_content_changed)
        outer.addWidget(self.content_edit)

        self._body_anim = QPropertyAnimation(self.content_edit, b"maximumHeight", self)
        self._body_anim.setDuration(160)
        self._body_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._actions_visible = False
        self._sync_actions()

    # --- hover-revealed actions -------------------------------------------

    def enterEvent(self, event) -> None:
        self._actions_visible = True
        self._sync_actions()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self.title_edit.hasFocus():
            self._actions_visible = False
            self._sync_actions()
        super().leaveEvent(event)

    def _sync_actions(self) -> None:
        visible = self._actions_visible or self.title_edit.hasFocus()
        for button in (self.reorder_btn, self.rename_btn, self.delete_btn):
            button.setVisible(visible)

    # --- read / edit states ------------------------------------------------

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only
        self.title_label.setText(self._title)
        self.title_label.setVisible(read_only)
        self.title_edit.setVisible(not read_only)
        self.title_edit.setReadOnly(read_only)
        self.title_edit.setProperty("readonly", "true" if read_only else "false")
        self.content_edit.setReadOnly(read_only)
        self.content_edit.setProperty("readonly", "true" if read_only else "false")
        if read_only:
            self.content_edit.setSizeAdjustPolicy(
                QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
            )
        else:
            self.content_edit.setSizeAdjustPolicy(
                QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
            )
            self.content_edit.setMinimumHeight(88)
        self._restyle()

    def _restyle(self) -> None:
        for widget in (self.title_edit, self.content_edit):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    # --- collapse / expand ------------------------------------------------

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._apply_expansion()

    def _apply_expansion(self) -> None:
        self.collapse_btn.setIcon(chevron_up() if self._expanded else chevron_down())
        self._body_anim.stop()
        if self._expanded:
            if self._read_only:
                self.content_edit.setMinimumHeight(0)
            else:
                self.content_edit.setMinimumHeight(88)
            self.content_edit.setMaximumHeight(_MAX_BODY_HEIGHT)
        else:
            self.content_edit.setMinimumHeight(0)
            self.content_edit.setMaximumHeight(0)
        self._body_anim.setStartValue(self.content_edit.maximumHeight())
        self._body_anim.setEndValue(_MAX_BODY_HEIGHT if self._expanded else 0)
        self._body_anim.start()

    # --- content -----------------------------------------------------------

    def set_content(self, content: str) -> None:
        self._suppress = True
        self.content_edit.setPlainText(content)
        self._suppress = False
        self._update_count(content)

    def _update_count(self, content: str) -> None:
        if not content.strip():
            self.count_badge.setText("")
            self.count_badge.setVisible(False)
            return
        lines = content.count("\n") + 1
        self.count_badge.setText(str(lines))
        self.count_badge.setVisible(True)

    def _on_title_edited(self) -> None:
        self.title_changed.emit(self.section_id, self.title_edit.text())

    def _on_content_changed(self) -> None:
        if self._suppress:
            return
        self._update_count(self.content_edit.toPlainText())
        self.content_changed.emit(self.section_id, self.content_edit.toPlainText())

    # --- section actions ---------------------------------------------------

    def _start_rename(self) -> None:
        if self._read_only:
            self.title_edit.setText(self._title)
            self.title_label.setVisible(False)
            self.title_edit.setVisible(True)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def _open_reorder_menu(self) -> None:
        menu = QMenu(self)
        up_action = menu.addAction("Move up")
        down_action = menu.addAction("Move down")
        chosen = menu.exec(self.reorder_btn.mapToGlobal(self.reorder_btn.rect().bottomLeft()))
        if chosen == up_action:
            self.move_requested.emit(self.section_id, -1)
        elif chosen == down_action:
            self.move_requested.emit(self.section_id, 1)
