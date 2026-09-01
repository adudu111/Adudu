"""Lookup popup: a floating, draggable, resizable information panel.

Frameless, always-on-top, rounded card with a draggable header ("Lookup" + close), a
scrollable body with a search-results state and a term-content state (dynamic accordion
sections — no hard-coded section names), and a fixed footer (keyboard hints + Edit +
Open Full Page). Used by the global hotkey, clipboard capture, and header search.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberglossary.services.lookup_service import LookupResult
from cyberglossary.services.search_service import SearchResult
from cyberglossary.ui import theme
from cyberglossary.ui.components import CategoryChip
from cyberglossary.ui.icons import (
    chevron_down,
    chevron_right,
    command_icon,
)
from cyberglossary.ui.icons import (
    close as close_icon,
)

_MARGIN = 8
_RESIZE_MARGIN = 6
_DEFAULT_WIDTH = 480
_DEFAULT_HEIGHT = 520


def clamp_popup_position(
    cursor_x: int,
    cursor_y: int,
    width: int,
    height: int,
    screen_geometry: tuple[int, int, int, int],
    margin: int = _MARGIN,
) -> tuple[int, int]:
    """Return a popup position near the cursor, clamped within the screen rectangle."""
    sx, sy, sw, sh = screen_geometry
    x = cursor_x + margin
    y = cursor_y + margin
    if x + width > sx + sw:
        x = cursor_x - width - margin
    if y + height > sy + sh:
        y = sy + sh - height - margin
    if x < sx:
        x = sx + margin
    if y < sy:
        y = sy + margin
    return x, y


def _screen_geometry_near(pos) -> tuple[int, int, int, int]:
    screen = QGuiApplication.screenAt(pos)
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    geometry = screen.availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()


class _TitleBar(QWidget):
    """Draggable title bar: press + move the native window via the window manager."""

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


class _PopupSection(QWidget):
    """A compact collapsible (accordion) section in the popup body (§18)."""

    def __init__(self, title: str, content: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.title = title
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        card = QFrame()
        card.setObjectName("sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 2, 8, 6)
        card_layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(4)

        self.chevron_btn = QToolButton()
        self.chevron_btn.setIcon(chevron_down())
        self.chevron_btn.setToolTip("Collapse / expand")
        self.chevron_btn.clicked.connect(self._toggle)
        header.addWidget(self.chevron_btn)

        self.header_btn = QPushButton(self.title)
        self.header_btn.setObjectName("popupSectionHeader")
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(True)
        self.header_btn.clicked.connect(self._on_toggled)
        header.addWidget(self.header_btn, 1)
        card_layout.addLayout(header)

        self.body = QLabel(content)
        self.body.setObjectName("popupSectionBody")
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(self.body)

        layout.addWidget(card)

    def _toggle(self) -> None:
        self._on_toggled(not self._expanded)

    def _on_toggled(self, checked: bool) -> None:
        self._expanded = checked
        self.header_btn.setChecked(checked)
        self.body.setVisible(checked)
        self.chevron_btn.setIcon(chevron_down() if checked else chevron_right())

    def is_expanded(self) -> bool:
        return self._expanded


class _ResultRow(QWidget):
    """A single search-result row in the popup's results state."""

    def __init__(self, result: SearchResult, query: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        if result.category:
            layout.addWidget(CategoryChip(result.category))

        name = QLabel(_highlight(result.term, query))
        name.setObjectName("termItemTitle")
        name.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(name, 1)

        if result.full_name:
            subtitle = QLabel(result.full_name)
            subtitle.setObjectName("termItemSubtitle")
            subtitle.setMaximumWidth(200)
            layout.addWidget(subtitle)


def _highlight(text: str, query: str) -> str:
    """Wrap the case-insensitive occurrence of ``query`` in ``text`` with an accent span."""
    escaped = html.escape(text or "")
    needle = (query or "").strip()
    if not needle:
        return escaped
    needle_escaped = html.escape(needle)
    lower = escaped.lower()
    index = lower.find(needle_escaped.lower())
    if index < 0:
        return escaped
    before = escaped[:index]
    match = escaped[index : index + len(needle_escaped)]
    after = escaped[index + len(needle_escaped) :]
    color = theme.accent_highlight()
    return f'{before}<span style="color:{color};">{match}</span>{after}'


class LookupPopup(QWidget):
    open_requested = Signal(int)
    edit_requested = Signal(int)
    add_term_requested = Signal(str)
    result_selected = Signal(int)  # a search result row was activated
    see_all_results_requested = Signal(str)  # query
    closed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("popup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 280)
        self._result: LookupResult | None = None
        self._sections: list[_PopupSection] = []
        self._mode = "term"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_RESIZE_MARGIN, _RESIZE_MARGIN, _RESIZE_MARGIN, _RESIZE_MARGIN)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("popupCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 110))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header: command icon + "Lookup" + close.
        self.title_bar = _TitleBar()
        self.title_bar.setObjectName("popupTitleBar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(16, 0, 8, 0)
        title_layout.setSpacing(8)

        command = QLabel()
        command.setPixmap(command_icon().pixmap(16, 16))
        title_layout.addWidget(command)

        head_label = QLabel("Lookup")
        head_label.setObjectName("popupTerm")
        title_layout.addWidget(head_label, 1)

        self.close_btn = QToolButton()
        self.close_btn.setIcon(close_icon())
        self.close_btn.setToolTip("Close · Esc")
        self.close_btn.clicked.connect(self.close_popup)
        title_layout.addWidget(self.close_btn)
        card_layout.addWidget(self.title_bar)

        # Body
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 8, 16, 8)
        self._content_layout.setSpacing(6)
        self._scroll.setWidget(self._content)
        card_layout.addWidget(self._scroll, 1)

        # Footer: hints + Edit + Open Full Page.
        self._action_bar = QWidget()
        self._action_bar.setObjectName("popupActionBar")
        self._action_layout = QHBoxLayout(self._action_bar)
        self._action_layout.setContentsMargins(16, 8, 16, 10)
        self._action_layout.setSpacing(8)
        card_layout.addWidget(self._action_bar)

        self._hints_label = QLabel("\u2191\u2193 navigate  \u00b7  \u21b5 open  \u00b7  ESC close")
        self._hints_label.setObjectName("countBadge")
        self.open_btn = None
        self.edit_btn = None
        self.add_btn = None

    # --- rendering --------------------------------------------------------

    def show_result(self, result: LookupResult) -> None:
        self._result = result
        self._mode = "term"
        self._clear()
        if result.found:
            self._build_found(result)
        else:
            self._build_not_found(result)

    def show_search_results(self, query: str, results: list[SearchResult]) -> None:
        self._result = None
        self._mode = "results"
        self._clear()
        self._build_results(query, results)

    def _clear(self) -> None:
        self._sections = []
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        while self._action_layout.count():
            item = self._action_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.open_btn = None
        self.edit_btn = None
        self.add_btn = None

    def _build_results(self, query: str, results: list[SearchResult]) -> None:
        if not results:
            message = QLabel(f'No results for "{query}"')
            message.setObjectName("muted")
            message.setWordWrap(True)
            self._content_layout.addWidget(message)
            self._content_layout.addStretch(1)
            self._hints_label.setVisible(False)
            return

        result_list = QListWidget()
        result_list.setObjectName("resultList")
        for result in results[:8]:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, result.term_id)
            row = _ResultRow(result, query)
            item.setSizeHint(row.sizeHint())
            result_list.addItem(item)
            result_list.setItemWidget(item, row)
        result_list.itemActivated.connect(
            lambda item: self.result_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        result_list.itemClicked.connect(
            lambda item: self.result_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        self._content_layout.addWidget(result_list)

        see_all_btn = QPushButton("See all results \u2192")
        see_all_btn.setObjectName("link")
        see_all_btn.clicked.connect(lambda: self.see_all_results_requested.emit(query))
        self._content_layout.addWidget(see_all_btn)

        self._action_layout.addWidget(self._hints_label, 1)
        self._hints_label.setVisible(True)

    def _build_found(self, result: LookupResult) -> None:
        self._title_label = QLabel(result.term or "")
        self._title_label.setObjectName("popupTerm")
        self._content_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(result.full_name or "")
        self._subtitle_label.setObjectName("muted")
        self._subtitle_label.setVisible(bool(result.full_name))
        self._content_layout.addWidget(self._subtitle_label)

        meta = QHBoxLayout()
        meta.setSpacing(6)
        self._category_badge = CategoryChip(result.category or "")
        if not result.category:
            self._category_badge.setVisible(False)
        meta.addWidget(self._category_badge)
        meta.addStretch(1)
        self._content_layout.addLayout(meta)

        for section in result.sections:
            self._content_layout.addWidget(self._divider())
            widget = _PopupSection(section.title, section.content)
            self._content_layout.addWidget(widget)
            self._sections.append(widget)
        self._content_layout.addStretch(1)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("ghost")
        self.open_btn = QPushButton("Open Full Page")
        self.open_btn.setObjectName("primary")
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(result.term_id))
        self.open_btn.clicked.connect(lambda: self.open_requested.emit(result.term_id))
        self._action_layout.addStretch(1)
        self._action_layout.addWidget(self.edit_btn)
        self._action_layout.addWidget(self.open_btn)
        self._hints_label.setVisible(False)

    def _build_not_found(self, result: LookupResult) -> None:
        self._title_label = QLabel(result.query or "")
        self._title_label.setObjectName("popupTerm")
        self._content_layout.addWidget(self._title_label)

        message = QLabel("Term not found in current profile.")
        message.setObjectName("muted")
        message.setWordWrap(True)
        self._content_layout.addWidget(message)
        self._content_layout.addStretch(1)

        self.add_btn = QPushButton("+ Add Term")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(lambda: self.add_term_requested.emit(result.query or ""))
        self._action_layout.addStretch(1)
        self._action_layout.addWidget(self.add_btn)
        self._hints_label.setVisible(False)

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("divider")
        return line

    # --- display / positioning --------------------------------------------

    def display(self, result: LookupResult) -> None:
        """Show the popup for a lookup; position only when it is not already visible."""
        self.show_result(result)
        if not self.isVisible():
            self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
            self._position_near_cursor()
        self.show()
        self.raise_()
        self.activateWindow()

    def show_under(self, widget: QWidget) -> None:
        """Position the popup under ``widget`` (e.g. the header search), right-aligned."""
        if not self.isVisible():
            self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
        global_pos = widget.mapToGlobal(widget.rect().bottomRight())
        geometry = _screen_geometry_near(global_pos)
        sx, sy, _sw, sh = geometry
        x = global_pos.x() - self.width()
        y = global_pos.y() + 4
        if x < sx:
            x = sx + _MARGIN
        if y + self.height() > sy + sh:
            y = sy + sh - self.height() - _MARGIN
        self.move(x, y)
        self.show()
        self.raise_()

    def show_near_cursor(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._position_near_cursor()

    def _position_near_cursor(self) -> None:
        pos = QCursor.pos()
        geometry = _screen_geometry_near(pos)
        x, y = clamp_popup_position(pos.x(), pos.y(), self.width(), self.height(), geometry)
        self.move(x, y)

    # --- resizing (8 directions) ------------------------------------------

    def _edges_at(self, pos) -> Qt.Edges:
        edges = Qt.Edges()
        if pos.x() <= _RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - _RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= _RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - _RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _cursor_for(self, edges: Qt.Edges) -> Qt.CursorShape:
        top = edges & Qt.Edge.TopEdge
        bottom = edges & Qt.Edge.BottomEdge
        left = edges & Qt.Edge.LeftEdge
        right = edges & Qt.Edge.RightEdge
        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._edges_at(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        edges = self._edges_at(event.position().toPoint())
        if edges:
            self.setCursor(self._cursor_for(edges))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    # --- lifecycle --------------------------------------------------------

    def close_popup(self) -> None:
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_popup()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        self.close_popup()
        super().focusOutEvent(event)
