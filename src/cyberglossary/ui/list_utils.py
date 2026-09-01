"""Reusable term-row widgets for lists.

Each row is a full-width card: an outer wrapper that stretches to the viewport width with
a 4px gap, containing an inner card frame (hover/selected states) with a leading 28px
hue tile (or folder/book icon), term name, inline category chip, and a secondary line.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.ui import theme
from cyberglossary.ui.icons import check as check_icon

_TILE_SIZE = 28
_ROW_GAP = 4
_ROW_MIN_HEIGHT = 44


class ElidedLabel(QLabel):
    """A single-line label that elides with an ellipsis and shows a full-text tooltip."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full_text = ""
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full_text = text or ""
        if self._full_text:
            self.setToolTip(self._full_text)
        else:
            self.setToolTip("")
        self._apply()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        if not self._full_text:
            super().setText("")
            return
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, max(0, self.width())
        )
        super().setText(elided)


class TermItemWidget(QWidget):
    """A full-width, two-line term row card."""

    def __init__(
        self,
        primary: str,
        secondary: str = "",
        category: str | None = None,
        tile_icon=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("termItemWrap")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._primary = primary
        self._multi = False
        self._row_icon = tile_icon

        wrap = QVBoxLayout(self)
        wrap.setContentsMargins(0, 0, 0, _ROW_GAP)
        wrap.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("termItem")
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(12, 5, 12, 5)
        card_layout.setSpacing(8)
        wrap.addWidget(self.card)

        self.tile = QLabel("")
        self.tile.setObjectName("termItemTile")
        self.tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tile.setFixedSize(_TILE_SIZE, _TILE_SIZE)
        if tile_icon is not None:
            self.tile.setPixmap(tile_icon.pixmap(16, 16))
        else:
            self.tile.setText(self._initial(primary))
        card_layout.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignVCenter)

        text_column = QVBoxLayout()
        text_column.setSpacing(1)
        text_column.setContentsMargins(0, 0, 0, 0)

        if not secondary:
            text_column.addStretch(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(primary)
        self.title.setObjectName("termItemTitle")
        name_row.addWidget(self.title, 1)

        self.chip = QLabel(category or "")
        self.chip.setObjectName("termItemChip")
        self.chip.setVisible(bool(category))
        name_row.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)
        text_column.addLayout(name_row)

        self.subtitle = ElidedLabel(secondary)
        self.subtitle.setObjectName("termItemSubtitle")
        if secondary:
            text_column.addWidget(self.subtitle)
        else:
            self.subtitle.hide()
            text_column.addStretch(1)
        card_layout.addLayout(text_column, 1)

        if category:
            hue = theme.category_hue(category)
            if hue is not None:
                index = theme.CATEGORY_HUES.index(hue)
                self.tile.setProperty("hue", str(index))
                self.chip.setProperty("hue", str(index))

    @staticmethod
    def _initial(text: str) -> str:
        return text.strip()[:1].upper() or "?"

    def set_selected(self, selected: bool) -> None:
        self.card.setProperty("selected", "true" if selected else "false")
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)

    def set_multi(self, multi: bool) -> None:
        """In multi-selection the leading tile becomes a checked box."""
        self._multi = multi
        if multi:
            self.tile.setProperty("check", "true")
            self.tile.setPixmap(check_icon().pixmap(14, 14))
        else:
            self.tile.setProperty("check", "false")
            if self._row_icon is not None:
                self.tile.setPixmap(self._row_icon.pixmap(16, 16))
            else:
                self.tile.clear()
                self.tile.setText(self._initial(self._primary))
        self.tile.style().unpolish(self.tile)
        self.tile.style().polish(self.tile)


class TermListWidget(QListWidget):
    """A QListWidget whose item widgets always stretch to the viewport width."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh_item_geometries)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refresh_item_geometries()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.schedule_refresh()

    def schedule_refresh(self) -> None:
        self._refresh_timer.start(0)

    def refresh_item_geometries(self) -> None:
        width = max(self.viewport().width(), 1)
        for index in range(self.count()):
            item = self.item(index)
            widget = self.itemWidget(item)
            if widget is None:
                continue
            height = max(_ROW_MIN_HEIGHT, widget.sizeHint().height())
            item.setSizeHint(QSize(width, height))
            widget.setGeometry(self.visualItemRect(item))


def add_term_item(
    list_widget: QListWidget,
    term_id: int,
    primary: str,
    secondary: str = "",
    category: str | None = None,
    tile_icon=None,
) -> QListWidgetItem:
    item = QListWidgetItem()
    item.setData(Qt.ItemDataRole.UserRole, term_id)
    width = max(list_widget.viewport().width(), 200)
    widget = TermItemWidget(primary, secondary, category, tile_icon)
    item.setSizeHint(QSize(width, max(_ROW_MIN_HEIGHT, widget.sizeHint().height())))
    list_widget.addItem(item)
    list_widget.setItemWidget(item, widget)
    return item


def sync_selection_highlight(list_widget: QListWidget) -> None:
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        widget = list_widget.itemWidget(item)
        if isinstance(widget, TermItemWidget):
            widget.set_selected(item.isSelected())


def sync_multi_highlight(list_widget: QListWidget, multi: bool) -> None:
    """Switch the leading tiles to checkbox look when multi-selecting."""
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        widget = list_widget.itemWidget(item)
        if isinstance(widget, TermItemWidget):
            widget.set_multi(multi and item.isSelected())


def visible_texts(list_widget: QListWidget) -> list[str]:
    """Return the primary visible text of each item (title for custom items)."""
    texts = []
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        widget = list_widget.itemWidget(item)
        if isinstance(widget, TermItemWidget):
            texts.append(widget.title.text())
        else:
            texts.append(item.text())
    return texts
