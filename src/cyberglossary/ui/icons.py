"""Minimal line icons drawn programmatically (no external assets)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

_MUTED = "#8D98AA"


def _icon(size: int, color: str, draw) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    draw(painter, size)
    painter.end()
    return QIcon(pixmap)


def search(color: str = _MUTED, size: int = 18) -> QIcon:
    def draw(p, s):
        p.drawEllipse(2, 2, s - 6, s - 6)
        p.drawLine(s - 5, s - 5, s - 1, s - 1)

    return _icon(size, color, draw)


def plus(color: str = "#ffffff", size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.25
        p.drawLine(s / 2, m, s / 2, s - m)
        p.drawLine(m, s / 2, s - m, s / 2)

    return _icon(size, color, draw)


def close(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.28
        p.drawLine(m, m, s - m, s - m)
        p.drawLine(s - m, m, m, s - m)

    return _icon(size, color, draw)


def chevron_down(color: str = _MUTED, size: int = 14) -> QIcon:
    def draw(p, s):
        m = s * 0.28
        p.drawLine(m, m, s / 2, s - m)
        p.drawLine(s / 2, s - m, s - m, m)

    return _icon(size, color, draw)


def chevron_up(color: str = _MUTED, size: int = 14) -> QIcon:
    def draw(p, s):
        m = s * 0.28
        p.drawLine(m, s - m, s / 2, m)
        p.drawLine(s / 2, m, s - m, s - m)

    return _icon(size, color, draw)


def chevron_right(color: str = _MUTED, size: int = 14) -> QIcon:
    def draw(p, s):
        m = s * 0.28
        p.drawLine(m, m, s - m, s / 2)
        p.drawLine(s - m, s / 2, m, s - m)

    return _icon(size, color, draw)


def list_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.22
        p.drawLine(m, s * 0.3, s - m, s * 0.3)
        p.drawLine(m, s * 0.5, s - m, s * 0.5)
        p.drawLine(m, s * 0.7, s - m, s * 0.7)

    return _icon(size, color, draw)


def folder_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.18
        p.drawLine(m, s * 0.32, m, s - m)
        p.drawLine(m, s - m, s - m, s - m)
        p.drawLine(s - m, s - m, s - m, s * 0.32)
        p.drawLine(m, s * 0.32, s * 0.34, s * 0.32)
        p.drawLine(s * 0.34, s * 0.32, s * 0.4, s * 0.22)
        p.drawLine(s * 0.4, s * 0.22, s * 0.58, s * 0.22)
        p.drawLine(s * 0.58, s * 0.22, s * 0.58, s * 0.32)

    return _icon(size, color, draw)


def sliders_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.2
        for y in (0.28, 0.5, 0.72):
            p.drawLine(m, s * y, s - m, s * y)
        p.drawEllipse(s * 0.62, s * 0.28 - 2, 4, 4)
        p.drawEllipse(s * 0.3, s * 0.5 - 2, 4, 4)
        p.drawEllipse(s * 0.5, s * 0.72 - 2, 4, 4)

    return _icon(size, color, draw)


def trash_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.22
        p.drawLine(m, s * 0.3, s - m, s * 0.3)
        p.drawLine(s * 0.3, s * 0.3, s * 0.3, s * 0.22)
        p.drawLine(s * 0.7, s * 0.3, s * 0.7, s * 0.22)
        p.drawLine(s * 0.26, s * 0.22, s * 0.74, s * 0.22)
        p.drawLine(s * 0.32, s * 0.3, s * 0.32, s - m)
        p.drawLine(s * 0.32, s - m, s - m, s - m)
        p.drawLine(s - m, s - m, s - m, s * 0.3)
        p.drawLine(s * 0.5, s * 0.42, s * 0.5, s * 0.8)

    return _icon(size, color, draw)


def pencil(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.18
        p.drawLine(m, s - m, s * 0.32, s - m)
        p.drawLine(s * 0.32, s - m, s - m, m)
        p.drawLine(s * 0.28, s * 0.62, s * 0.62, s * 0.28)
        p.drawLine(s * 0.62, s * 0.28, s * 0.68, s * 0.34)
        p.drawLine(s * 0.34, s * 0.68, s * 0.28, s * 0.62)
        p.drawLine(s * 0.68, s * 0.34, s - m, s - m)
        p.drawLine(s * 0.68, s * 0.34, s - m, s * 0.34)

    return _icon(size, color, draw)


def more_horizontal(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        for x in (0.22, 0.5, 0.78):
            p.drawEllipse(s * x - 1.5, s * 0.5 - 1.5, 3, 3)

    return _icon(size, color, draw)


def check(color: str = "#ffffff", size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.2
        p.drawLine(m, s * 0.5, s * 0.42, s * 0.72)
        p.drawLine(s * 0.42, s * 0.72, s - m, m)

    return _icon(size, color, draw)


def sort_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.22
        p.drawLine(m, s * 0.3, s * 0.5, s * 0.12)
        p.drawLine(s * 0.5, s * 0.12, s - m, s * 0.3)
        p.drawLine(m, s * 0.7, s * 0.5, s * 0.88)
        p.drawLine(s * 0.5, s * 0.88, s - m, s * 0.7)

    return _icon(size, color, draw)


def filter_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.22
        p.drawLine(m, m, s - m, s - m)
        p.drawLine(m, s - m, s - m, m)
        p.drawEllipse(s * 0.5 - 2, s * 0.5 - 2, 4, 4)

    return _icon(size, color, draw)


def moon_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.2
        p.drawArc(m, m, s * 0.6, s * 0.6, 45 * 16, 200 * 16)
        p.drawLine(s * 0.7, s * 0.26, s * 0.78, s * 0.2)

    return _icon(size, color, draw)


def sun_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.24
        p.drawEllipse(m, m, s - 2 * m, s - 2 * m)
        for a in range(0, 360, 45):
            import math

            x1 = s / 2 + math.cos(math.radians(a)) * (s * 0.32)
            y1 = s / 2 + math.sin(math.radians(a)) * (s * 0.32)
            x2 = s / 2 + math.cos(math.radians(a)) * (s * 0.44)
            y2 = s / 2 + math.sin(math.radians(a)) * (s * 0.44)
            p.drawLine(x1, y1, x2, y2)

    return _icon(size, color, draw)


def chevrons_up_down(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.24
        p.drawLine(m, s * 0.28, s / 2, s * 0.12)
        p.drawLine(s / 2, s * 0.12, s - m, s * 0.28)
        p.drawLine(m, s * 0.72, s / 2, s * 0.88)
        p.drawLine(s / 2, s * 0.88, s - m, s * 0.72)

    return _icon(size, color, draw)


def book_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.2
        p.drawLine(s / 2, m, s / 2, s - m)
        p.drawArc(m, m, s / 2 - m, s - 2 * m, 90 * 16, 180 * 16)
        p.drawArc(s / 2, m, s / 2 - m, s - 2 * m, 90 * 16, 180 * 16)

    return _icon(size, color, draw)


def sidebar_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.24
        p.drawLine(m, m, s - m, m)
        p.drawLine(m, s * 0.5, s - m, s * 0.5)
        p.drawLine(m, s - m, s - m, s - m)
        p.drawLine(m, m, m, s - m)

    return _icon(size, color, draw)


def dot_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        painter_pen = p.pen()
        painter_pen.setWidthF(1.4)
        p.setPen(painter_pen)
        p.setBrush(painter_pen.color())
        p.drawEllipse(s * 0.3, s * 0.3, s * 0.4, s * 0.4)

    return _icon(size, color, draw)


def user_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        p.drawEllipse(s * 0.38, s * 0.16, s * 0.24, s * 0.24)
        p.drawArc(s * 0.24, s * 0.42, s * 0.52, s * 0.5, 180 * 16, 180 * 16)

    return _icon(size, color, draw)


def command_icon(color: str = _MUTED, size: int = 16) -> QIcon:
    def draw(p, s):
        m = s * 0.18
        # Command key symbol: four loops meeting at the center.
        p.drawArc(m, m, s * 0.64, s * 0.64, 60 * 16, 240 * 16)
        p.drawArc(m, m, s * 0.64, s * 0.64, 300 * 16, 240 * 16)
        p.drawArc(m + s * 0.36, m, s * 0.64, s * 0.64, 60 * 16, 240 * 16)
        p.drawArc(m + s * 0.36, m, s * 0.64, s * 0.64, 300 * 16, 240 * 16)

    return _icon(size, color, draw)


def alert_icon(color: str = _MUTED, size: int = 20) -> QIcon:
    def draw(p, s):
        p.drawLine(s / 2, s * 0.2, s / 2, s * 0.62)
        p.drawLine(s / 2, s * 0.78, s / 2, s * 0.8)
        p.drawLine(s * 0.16, s * 0.85, s * 0.5, s * 0.14)
        p.drawLine(s * 0.5, s * 0.14, s * 0.84, s * 0.85)
        p.drawLine(s * 0.84, s * 0.85, s * 0.16, s * 0.85)

    return _icon(size, color, draw)
