"""Reusable presentation components: chips, empty states, eyebrows, flow layout.

Shared by the term list, term detail workspace, lookup popup, and dialogs so every
surface speaks the same design language (DESIGN.md §22, §23).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.ui import theme
from cyberglossary.ui.icons import close as close_icon


class FlowLayout(QLayout):
    """A wrapping layout for chip rows (§12.5)."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 6):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_space = spacing
        self._v_space = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_space
            if next_x - self._h_space > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + self._v_space
                next_x = x + hint.width() + self._h_space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class Eyebrow(QLabel):
    """Uppercase section label: 11px, muted, letter-spaced (§5.2 font-xs)."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text.upper(), parent)
        self.setObjectName("sectionLabel")


class AliasChip(QFrame):
    """A compact alias chip (§23); optionally removable with an embedded x button."""

    remove_requested = Signal()

    def __init__(self, text: str, removable: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("aliasChip")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 4 if removable else 8, 2)
        row.setSpacing(2)
        label = QLabel(text)
        row.addWidget(label)
        if removable:
            button = QToolButton()
            button.setIcon(close_icon())
            button.setFixedSize(18, 18)
            button.setToolTip("Remove alias")
            button.clicked.connect(self.remove_requested.emit)
            row.addWidget(button)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy()
        )


class CategoryChip(QLabel):
    """A hue-colored category pill derived from the category name (§4.6)."""

    def __init__(self, name: str, parent: QWidget | None = None):
        super().__init__(name, parent)
        self.setObjectName("termItemChip")
        hue = theme.category_hue(name)
        if hue is not None:
            self.setProperty("hue", str(theme.CATEGORY_HUES.index(hue)))


class Switch(QCheckBox):
    """A compact toggle switch (38x22) used by the settings dialog (§21)."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setChecked(checked)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = theme._DARK_COLORS if theme._current_mode == theme.DARK else theme._LIGHT_COLORS
        track = QColor(colors["accent_blue_strong"] if self.isChecked() else colors["border"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRect(0, 0, 38, 22), 11, 11)
        knob_x = 19 if self.isChecked() else 2
        painter.setBrush(QColor(colors["text_inverse"]))
        painter.drawEllipse(QPoint(knob_x + 9, 11), 9, 9)
        painter.end()


class EmptyState(QWidget):
    """Centered empty-state block: faded brand tile + title + secondary hint (§22)."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        tile_text: str = "A",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)

        tile = QLabel(tile_text)
        tile.setObjectName("emptyTile")
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setFixedSize(40, 40)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(tile)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("emptyTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("emptySubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        if subtitle:
            outer.addWidget(self.subtitle_label)

        self.action_btn = QPushButton("")
        self.action_btn.setObjectName("ghost")
        self.action_btn.setFixedHeight(28)
        self.action_btn.setVisible(False)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.action_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        outer.addStretch(1)

    def set_text(self, title: str, subtitle: str = "", action: str | None = None) -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))
        if action:
            self.action_btn.setText(action)
            self.action_btn.setVisible(True)
        else:
            self.action_btn.setVisible(False)
