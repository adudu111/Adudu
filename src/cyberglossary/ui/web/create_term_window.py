"""Standalone "New Term" creation window (frameless ``QWebEngineView``).

Opened by the lookup popup's Create button (and the main window's "New term") as a
small floating window — not the whole application. Shares the existing ``Bridge`` and
reuses the ``createTerm`` / ``addSection`` / ``getCategories`` slots. Supports drag,
edge/corner resize, and close.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from cyberglossary.ui.web.bridge import Bridge

_WIDTH = 440
_HEIGHT = 620
_MARGIN = 8

_EDGES = {
    "n": Qt.Edge.TopEdge,
    "s": Qt.Edge.BottomEdge,
    "e": Qt.Edge.RightEdge,
    "w": Qt.Edge.LeftEdge,
    "ne": Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    "nw": Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
    "se": Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
    "sw": Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
}


class CreateTermWindow(QWebEngineView):
    def __init__(self, bridge: Bridge, web_dir: Path):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(_WIDTH, _HEIGHT)
        self.setMinimumSize(360, 300)

        self.bridge = bridge
        self._positioned = False

        self.setPage(QWebEnginePage(self))
        self.page().setBackgroundColor(QColor(0, 0, 0, 0))
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self.channel = QWebChannel(self.page())
        self.channel.registerObject("bridge", bridge)
        self.page().setWebChannel(self.channel)

        self.load(QUrl.fromLocalFile(str((web_dir / "create_term.html").resolve())))

    def show_create_term(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        if not self._positioned:
            self._place_near_cursor()
            self._positioned = True

    def _place_near_cursor(self) -> None:
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = pos.x() + _MARGIN
        y = pos.y() + _MARGIN
        if x + self.width() > g.x() + g.width():
            x = pos.x() - self.width() - _MARGIN
        if y + self.height() > g.y() + g.height():
            y = g.y() + g.height() - self.height() - _MARGIN
        self.move(max(g.x(), x), max(g.y(), y))

    def close_create_term(self) -> None:
        self.hide()

    def start_move(self) -> None:
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def start_resize(self, edge: str) -> None:
        edges = _EDGES.get(edge)
        if edges is None:
            return
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemResize(edges)
