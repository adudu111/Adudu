"""Standalone frameless lookup popup (DESIGN.md §20).

A separate, always-on-top ``QWebEngineView`` that renders only the HTML lookup popup,
independent of the main application window. When the global hotkey fires, this popup is
shown (not the main window) with the resolved lookup result. Drag to move; Esc / the
close button hide it; Open Full Page / Edit hand the term back to the main window.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from cyberglossary.ui.web.bridge import Bridge

_DEFAULT_WIDTH = 480
_DEFAULT_HEIGHT = 520
_COMPACT_WIDTH = 420
_COMPACT_HEIGHT = 240
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


class LookupPopupWindow(QWebEngineView):
    def __init__(self, bridge: Bridge, web_dir: Path):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
        self.setMinimumSize(320, 240)

        self.bridge = bridge
        self._bridge_ready = False
        self._pending: list[str] = []
        self._positioned = False
        self._compact = False

        self.setPage(QWebEnginePage(self))
        # Let the page render truly transparent so the rounded `.lookup` corners show
        # through the frameless window (no opaque white fill behind them).
        self.page().setBackgroundColor(QColor(0, 0, 0, 0))
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self.channel = QWebChannel(self.page())
        self.channel.registerObject("bridge", bridge)
        self.page().setWebChannel(self.channel)

        self.load(QUrl.fromLocalFile(str((web_dir / "popup.html").resolve())))

    # --- readiness / result -------------------------------------------------

    def on_bridge_ready(self) -> None:
        self._bridge_ready = True
        for payload in self._pending:
            self.bridge.lookupResult.emit(payload)
        self._pending = []

    def show_result(self, payload_json: str) -> None:
        if self._bridge_ready:
            self.bridge.lookupResult.emit(payload_json)
        else:
            self._pending.append(payload_json)
        # A not-found lookup is compact; a found shift back to the default size.
        found = json.loads(payload_json).get("found", False)
        if found:
            if self._compact:
                self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
                self._compact = False
        else:
            self.resize(_COMPACT_WIDTH, _COMPACT_HEIGHT)
            self._compact = True
        self._show_and_position()

    def _show_and_position(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        if self._positioned:
            # Keep the size/position the user chose (drag/resize) while open and
            # across re-shows; only auto-place the very first time.
            return
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
        self._positioned = True

    def close_popup(self) -> None:
        self.hide()

    # --- native drag / resize (driven from JS pointer handlers) -------------

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
