"""Global search launcher — a separate frameless ``QWebEngineView`` window.

Distinct from the lookup popup: opened by a *second* global hotkey, it searches the whole
knowledge base (categories first, then terms/commands) and shows a detail panel. It shares
the existing ``Bridge``/services/FTS5 — this module is only the window shell.

Supports: always-on-top, drag, edge/corner resize, an expanded state, and a minimized
floating bar (the page collapses its DOM and the window shrinks to a short bar). Closing
destroys the launcher; the hotkey lazily re-creates it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from cyberglossary.ui.web.bridge import Bridge

_EXPANDED_WIDTH = 640
_EXPANDED_HEIGHT = 560
_MIN_WIDTH = 520
_MIN_HEIGHT = 48
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


class LauncherWindow(QWebEngineView):
    def __init__(self, bridge: Bridge, web_dir: Path):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(_EXPANDED_WIDTH, _EXPANDED_HEIGHT)
        self.setMinimumSize(300, _MIN_HEIGHT)

        self.bridge = bridge
        self._positioned = False
        self._minimized = False
        self._expanded_size = (_EXPANDED_WIDTH, _EXPANDED_HEIGHT)

        self.setPage(QWebEnginePage(self))
        self.page().setBackgroundColor(QColor(0, 0, 0, 0))
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self.channel = QWebChannel(self.page())
        self.channel.registerObject("bridge", bridge)
        self.page().setWebChannel(self.channel)

        self.load(QUrl.fromLocalFile(str((web_dir / "launcher.html").resolve())))

    # --- show / state ------------------------------------------------------

    def show_launcher(self) -> None:
        self.restore()
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

    def minimize(self) -> None:
        if self._minimized:
            return
        self._expanded_size = (self.width(), self.height())
        self._minimized = True
        self.resize(_MIN_WIDTH, _MIN_HEIGHT)

    def restore(self) -> None:
        if not self._minimized:
            return
        self._minimized = False
        self.resize(*self._expanded_size)

    def close_launcher(self) -> None:
        self.hide()

    # --- native drag / resize ---------------------------------------------

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
