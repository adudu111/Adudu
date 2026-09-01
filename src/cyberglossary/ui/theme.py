"""Theming: a calm, dense, pro-grade design system for adudu.

Centralizes every visual token (colors, spacing, radius, typography, heights) from
``DESIGN.md`` as Python constants — the single source of truth for the presentation layer.
The global QSS is generated from those tokens so no stray hex values live in widget code.
"""

from __future__ import annotations

import zlib

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

DARK = "dark"
LIGHT = "light"

_current_mode = DARK


# --- Color tokens (§4) -----------------------------------------------------

# Dark theme is the primary visual reference. Neutrals are navy-tinted, never pure gray.
_DARK_COLORS: dict[str, str] = {
    # base / neutrals
    "bg_base": "#0B0F16",
    "bg_deep": "#070A10",
    "surface": "#0F141D",
    "surface_raised": "#141B26",
    "surface_hover": "#1A2230",
    "surface_active": "#1E2836",
    "overlay_scrim": "rgba(4, 7, 12, 0.55)",
    "overlay_popup": "rgba(7, 10, 16, 0.85)",
    # borders
    "border_subtle": "#1A222F",
    "border": "#232E40",
    "border_strong": "#2E3C52",
    "border_accent": "rgba(74, 127, 255, 0.45)",
    # text
    "text_primary": "#E8EEF7",
    "text_secondary": "#9AA7B8",
    "text_muted": "#7C8AA0",
    "text_disabled": "#4A576D",
    "text_inverse": "#FFFFFF",
    "text_on_deep": "#0B0F16",
    # accents
    "accent_blue": "#4A7FFF",
    "accent_blue_strong": "#3B6EE8",
    "accent_blue_hover": "#3362D8",
    "accent_blue_active": "#2B55C2",
    "accent_blue_soft": "rgba(74, 127, 255, 0.14)",
    "accent_blue_text": "#8FB0FF",
    "accent_purple": "#8B7CF6",
    "accent_purple_soft": "rgba(139, 124, 246, 0.14)",
    # status
    "success": "#2FBF71",
    "warning": "#F5A524",
    "danger": "#F05252",
    "danger_hover": "#D94444",
    "danger_active": "#B83A3A",
    "danger_soft": "rgba(240, 82, 82, 0.12)",
    "info": "#38BDF8",
}

_LIGHT_COLORS: dict[str, str] = {
    "bg_base": "#F6F8FB",
    "bg_deep": "#EDF1F7",
    "surface": "#FFFFFF",
    "surface_raised": "#FFFFFF",
    "surface_hover": "#EEF2F8",
    "surface_active": "#E4EAF3",
    "overlay_scrim": "rgba(20, 26, 38, 0.35)",
    "overlay_popup": "rgba(255, 255, 255, 0.92)",
    "border_subtle": "#E3E8EF",
    "border": "#D3DBE6",
    "border_strong": "#B9C4D4",
    "border_accent": "rgba(46, 91, 208, 0.45)",
    "text_primary": "#161C26",
    "text_secondary": "#4A5568",
    "text_muted": "#6B7688",
    "text_disabled": "#A8B0BE",
    "text_inverse": "#FFFFFF",
    "text_on_deep": "#FFFFFF",
    "accent_blue": "#3B6EE8",
    "accent_blue_strong": "#2E5BD0",
    "accent_blue_hover": "#274EC0",
    "accent_blue_active": "#2346A8",
    "accent_blue_soft": "rgba(46, 91, 208, 0.14)",
    "accent_blue_text": "#2E5BD0",
    "accent_purple": "#7B68E8",
    "accent_purple_soft": "rgba(123, 104, 232, 0.14)",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_active": "#991B1B",
    "danger_soft": "rgba(220, 38, 38, 0.12)",
    "info": "#0284C7",
}

# --- Category hue table (§4.6) ---------------------------------------------

# (chip fill @ 16% alpha, chip text) — presentation-only, derived from the name.
CATEGORY_HUES: tuple[tuple[str, str], ...] = (
    ("rgba(74, 127, 255, 0.16)", "#7FA8FF"),  # cat-blue
    ("rgba(139, 124, 246, 0.16)", "#A99EFF"),  # cat-purple
    ("rgba(56, 189, 248, 0.16)", "#67D2FB"),  # cat-cyan
    ("rgba(47, 191, 113, 0.16)", "#5EDC9A"),  # cat-green
    ("rgba(245, 165, 36, 0.16)", "#FFC45C"),  # cat-amber
    ("rgba(236, 106, 155, 0.16)", "#F28FB4"),  # cat-pink
)


def category_hue(name: str) -> tuple[str, str] | None:
    """Return the deterministic ``(fill, text)`` hue pair for a category name.

    Uses ``zlib.crc32`` so the mapping is stable across runs (§4.6).
    """
    if not name:
        return None
    index = zlib.crc32(name.lower().encode("utf-8")) % len(CATEGORY_HUES)
    return CATEGORY_HUES[index]


def accent_highlight() -> str:
    """Return the current theme's accent-blue text color (for matched-substring highlights)."""
    colors = _DARK_COLORS if _current_mode == DARK else _LIGHT_COLORS
    return colors["accent_blue_text"]


# --- Global stylesheet -----------------------------------------------------

_QSS = """
* { font-family: "Segoe UI", "Segoe UI Variable", sans-serif; font-size: 13px; }
QMainWindow, QWidget { background: __bg_base__; color: __text_primary__; }
QWidget#app { background: __bg_base__; }

/* --- menu bar (§13.1) --- */
QMenuBar {
    background: __bg_deep__; border-bottom: 1px solid __border_subtle__;
    min-height: 28px; padding: 0 4px;
}
QMenuBar::item { background: transparent; color: __text_secondary__; padding: 4px 10px; border-radius: 6px; }
QMenuBar::item:selected { background: __surface_hover__; color: __text_primary__; }
QMenuBar::item:pressed { background: __accent_blue_soft__; color: __text_primary__; }
QMenu {
    background: __surface_raised__; color: __text_primary__;
    border: 1px solid __border__; border-radius: 8px; padding: 6px;
}
QMenu::item { color: __text_secondary__; padding: 6px 12px; border-radius: 6px; min-width: 200px; }
QMenu::item:selected { background: __surface_hover__; color: __text_primary__; }
QMenu::separator { height: 1px; background: __border_subtle__; margin: 4px 8px; }

/* --- header (§13) --- */
QFrame#header { background: __surface__; border-bottom: 1px solid __border_subtle__; }
QLabel#pageTitle { font-size: 15px; font-weight: 600; color: __text_primary__; }
QLabel#crumbRoot { color: __text_secondary__; font-size: 13px; }
QLabel#crumbSep { color: __text_muted__; font-size: 13px; }
QLabel#breadcrumb { color: __text_secondary__; font-size: 13px; }

/* --- sidebar (§14) --- */
QFrame#sidebar { background: __surface__; border-right: 1px solid __border_subtle__; }
QLabel#brandTile {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4A7FFF, stop:1 #8B7CF6);
    color: #0B0F16; border-radius: 6px; font-weight: 600; font-size: 13px;
}
QLabel#brandName { font-size: 15px; font-weight: 600; color: __text_primary__; }
QLabel#brandVersion { color: __text_muted__; font-size: 11px; }
QLabel#sectionLabel {
    color: __text_muted__; font-size: 11px; font-weight: 500; letter-spacing: 1px;
    padding: 12px 12px 6px 12px;
}

/* --- labels --- */
QLabel#listTitle { font-size: 15px; font-weight: 600; color: __text_primary__; }
QLabel#sectionTitle { font-size: 15px; font-weight: 600; color: __text_primary__; }
QLabel#popupTerm { font-size: 17px; font-weight: 600; color: __text_primary__; }
QLabel#termDisplayTitle { font-size: 20px; font-weight: 600; color: __text_primary__; }
QLabel#termDisplaySubtitle { color: __text_secondary__; font-size: 13px; }
QLabel#detailsFootnote { color: __text_muted__; font-size: 11px; font-family: "Cascadia Mono", "Consolas", monospace; }
QLabel#detailsFootnoteCat { color: __text_muted__; font-size: 11px; font-family: "Cascadia Mono", "Consolas", monospace; }
QLabel#previewTag {
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 11px;
    color: __accent_blue_text__; background: __accent_blue_soft__;
    border: 1px solid __border_accent__; border-radius: 999px; padding: 2px 8px;
}
QLabel#aliasesLabel { color: __text_muted__; font-size: 11px; }
QLabel#muted { color: __text_muted__; }
QLabel#countBadge { color: __text_muted__; font-family: "Cascadia Mono", "Consolas", monospace; font-size: 11px; }
QLabel#kbdChip {
    color: __text_muted__; background: __bg_deep__; border: 1px solid __border_subtle__;
    border-radius: 3px; padding: 2px 4px; font-family: "Cascadia Mono", "Consolas", monospace; font-size: 11px;
}
QLabel#emptyTile {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(74, 127, 255, 0.35), stop:1 rgba(139, 124, 246, 0.35));
    color: __text_muted__; border-radius: 10px; font-weight: 700; font-size: 16px;
}
QLabel#emptyTitle { font-size: 15px; font-weight: 600; color: __text_primary__; }
QLabel#emptySubtitle { color: __text_secondary__; font-size: 13px; }

/* --- cards --- */
QFrame#popupCard { background: __surface_raised__; border: 1px solid __border__; border-radius: 8px; }
QFrame#sectionCard { background: __surface_raised__; border: 1px solid __border_subtle__; border-radius: 8px; }
QFrame#selectionBar { background: __surface_raised__; border: 1px solid __border__; border-radius: 8px; }
QWidget#toc {
    background: __surface__; border-left: 1px solid __border_subtle__;
    border-radius: 8px; padding: 8px;
}
QFrame#divider { color: __border_subtle__; }
QFrame#emptyWell { background: __bg_deep__; border: 1px dashed __border_subtle__; border-radius: 8px; }

/* --- buttons (§11) --- */
/* Qt adds QSS padding+border on top of min-height; vertical padding is 0. */
QPushButton {
    background: __surface_raised__; color: __text_primary__;
    border: 1px solid __border__; border-radius: 6px; padding: 0px 14px; min-height: 30px;
}
QPushButton:hover { background: __surface_hover__; border-color: __border_strong__; }
QPushButton:pressed { background: __surface_active__; }
QPushButton:disabled { color: __text_disabled__; background: transparent; border-color: __border_subtle__; }
QPushButton#primary {
    background: __accent_blue_strong__; color: __text_inverse__; border: 1px solid transparent;
    min-height: 30px; padding: 0px 16px; font-weight: 600;
}
QPushButton#primary:hover { background: __accent_blue_hover__; }
QPushButton#primary:pressed { background: __accent_blue_active__; }
QPushButton#primary:disabled { background: __border__; color: __text_disabled__; }
QPushButton#ghost { background: transparent; color: __text_secondary__; border: none; padding: 0px 10px; min-height: 28px; }
QPushButton#ghost:hover { background: __surface_hover__; color: __text_primary__; }
QPushButton#ghost:pressed { background: __surface_active__; }
QPushButton#danger {
    color: __text_inverse__; background: __danger__; border: 1px solid transparent;
    min-height: 30px; padding: 0px 16px; font-weight: 600;
}
QPushButton#danger:hover { background: __danger_hover__; }
QPushButton#danger:pressed { background: __danger_active__; }
QPushButton#dangerOutline { color: __danger__; border-color: __border__; background: transparent; }
QPushButton#dangerOutline:hover { background: __danger_soft__; border-color: __danger__; }
QPushButton#link { background: transparent; color: __accent_blue_text__; border: none; padding: 0px; min-height: 0px; }
QPushButton#link:hover { color: __accent_blue__; text-decoration: underline; }
QPushButton#nav {
    background: transparent; color: __text_secondary__; border: none;
    text-align: left; padding: 0px 12px; border-radius: 6px; min-height: 30px;
}
QPushButton#nav:hover { background: __surface_hover__; color: __text_primary__; }
QPushButton#nav:checked {
    background: __accent_blue_soft__; color: __text_primary__;
    border-left: 3px solid __accent_purple__; padding: 0px 9px;
}
QPushButton#addSectionBtn {
    background: transparent; border: 1px dashed __border__; border-radius: 8px;
    color: __text_secondary__; min-height: 36px; font-weight: 500; padding: 0px 16px;
}
QPushButton#addSectionBtn:hover { border-color: __border_strong__; background: __surface_hover__; color: __text_primary__; }

/* --- inputs (§12) --- */
/* Qt adds QSS padding+border on top of min-height, so vertical padding is 0 here. */
QLineEdit, QComboBox {
    background: __surface_raised__; color: __text_primary__;
    border: 1px solid __border_subtle__; border-radius: 6px;
    padding: 0px 8px; min-height: 30px;
    selection-background-color: __accent_blue__;
}
QPlainTextEdit {
    background: __surface_raised__; color: __text_primary__;
    border: 1px solid __border_subtle__; border-radius: 6px; padding: 6px 8px;
    selection-background-color: __accent_blue__;
}
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover { border: 1px solid __border_strong__; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid __border_accent__; }
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled { background: __bg_base__; color: __text_disabled__; }
QLineEdit#search, QLineEdit#filter {
    background: __surface_raised__; border: 1px solid __border_subtle__;
    border-radius: 16px; padding: 0px 14px; min-height: 30px;
}
QLineEdit#search:focus, QLineEdit#filter:focus { border: 1px solid __border_accent__; }
QComboBox#profileCombo {
    background: transparent; border: none; padding: 0px 4px; min-height: 26px;
}
QComboBox#profileCombo:hover { background: __surface_hover__; border-radius: 6px; }
QComboBox#profileCombo::drop-down { border: none; width: 20px; }
QLineEdit#termTitleEdit {
    background: transparent; border: 1px solid transparent;
    font-size: 20px; font-weight: 600; color: __text_primary__; padding: 0px 6px; min-height: 30px; border-radius: 6px;
}
QLineEdit#termTitleEdit:hover { background: __surface_raised__; border-color: __border_subtle__; }
QLineEdit#termTitleEdit:focus { background: __surface_raised__; border: 1px solid __border_accent__; }
QLineEdit#sectionTitleEdit {
    background: transparent; border: 1px solid transparent;
    font-weight: 600; color: __text_primary__; padding: 0px 6px; min-height: 24px; border-radius: 6px;
}
QLineEdit#sectionTitleEdit:hover { background: __surface_raised__; border-color: __border_subtle__; }
QLineEdit#sectionTitleEdit:focus { background: __surface_raised__; border: 1px solid __border_accent__; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: __surface_raised__; color: __text_primary__; border: 1px solid __border__;
    selection-background-color: __accent_blue_soft__; border-radius: 8px; padding: 4px;
}

/* --- lists (§15) --- */
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 0px; margin: 2px 0px; background: transparent; border: none; }
QListWidget::item:hover { background: transparent; }
QListWidget::item:selected { background: transparent; color: __text_primary__; }

/* --- two-line term item cards --- */
QFrame#termItem { background: __surface_raised__; border: 1px solid __border_subtle__; border-radius: 8px; }
QFrame#termItem[selected="true"] {
    background: __accent_blue_soft__; border: 1px solid rgba(74, 127, 255, 0.40);
    border-left: 2px solid __accent_blue__;
}
QFrame#termItem:hover { background: __surface_hover__; border-color: __border_strong__; }
QFrame#termItem[selected="true"]:hover { background: __accent_blue_soft__; }
QLabel#termItemTitle { font-weight: 600; color: __text_primary__; background: transparent; }
QLabel#termItemSubtitle { color: __text_muted__; font-size: 12px; background: transparent; }
QLabel#termItemTile {
    border-radius: 6px; font-weight: 600; font-size: 12px;
    background: __bg_deep__; color: __text_secondary__;
}
QLabel#termItemTile[check="true"] { background: __accent_blue__; color: __text_inverse__; }
QLabel#termItemChip {
    border-radius: 999px; padding: 1px 8px; font-size: 11px; font-weight: 600;
    background: __accent_purple_soft__; color: __accent_blue_text__;
}

/* --- alias chips (§23) --- */
QFrame#aliasChip {
    background: __bg_deep__; border: 1px solid __border_subtle__; border-radius: 3px;
}
QFrame#aliasChip QLabel { color: __text_secondary__; font-size: 11px; background: transparent; }

/* --- popup accordion header (compact variant, §18) --- */
QPushButton#popupSectionHeader {
    background: transparent; color: __text_primary__; border: none; text-align: left;
    border-radius: 6px; padding: 6px 10px; min-height: 36px; font-weight: 600;
}
QPushButton#popupSectionHeader:hover { background: __surface_hover__; }
QLabel#popupSectionBody { color: __text_primary__; padding: 0 10px 8px 10px; }

/* --- read-only display text (document style, §17.1) --- */
QPlainTextEdit[readonly="true"] { background: transparent; border: 1px solid transparent; padding: 0px; }
QLineEdit#sectionTitleEdit[readonly="true"] {
    background: transparent; border: 1px solid transparent;
}
QLineEdit#sectionTitleEdit[readonly="true"]:hover { background: transparent; border: 1px solid transparent; }
QLineEdit#sectionTitleEdit[readonly="true"]:focus { background: transparent; border: 1px solid transparent; }

/* --- tool buttons --- */
QToolButton {
    background: transparent; color: __text_muted__; border: none;
    border-radius: 6px; padding: 5px;
}
QToolButton:hover { background: __surface_hover__; color: __text_primary__; }
QToolButton:pressed { background: __surface_active__; }

/* --- scroll --- */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 10px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: __border_strong__; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: __text_muted__; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 10px; background: transparent; margin: 2px; }
QScrollBar::handle:horizontal { background: __border_strong__; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* --- splitter --- */
QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: __surface_active__; }

/* --- tooltip --- */
QToolTip { background: __surface_raised__; color: __text_primary__; border: 1px solid __border__; padding: 6px 10px; }

/* --- message box / dialog --- */
QDialog { background: __bg_base__; }
QMessageBox { background: __surface__; }
QFrame#dialogCard {
    background: __surface_raised__; border: 1px solid __border__; border-radius: 8px;
}
QWidget#dialogTitleBar { background: __surface__; border-bottom: 1px solid __border_subtle__; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QLabel#dialogTitle { color: __text_primary__; font-weight: 600; font-size: 13px; }
QWidget#dialogFooter { border-top: 1px solid __border_subtle__; }
"""


def _hue_qss() -> str:
    """Generate category-hue style rules for tiles/chips (§4.6, §23)."""
    rules = []
    for index, (fill, text) in enumerate(CATEGORY_HUES):
        rules.append(
            f'QLabel#termItemTile[hue="{index}"], QLabel#termItemChip[hue="{index}"] '
            f'{{ background: {fill}; color: {text}; }}'
        )
    return "\n".join(rules)


def _qss(colors: dict[str, str]) -> str:
    qss = _QSS
    for key, value in colors.items():
        qss = qss.replace(f"__{key}__", value)
    return qss + "\n" + _hue_qss()


def apply_theme(app: QApplication, mode: str) -> str:
    """Apply the given theme to the application and return the applied mode."""
    global _current_mode
    mode = mode if mode in (DARK, LIGHT) else DARK
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    colors = _DARK_COLORS if mode == DARK else _LIGHT_COLORS
    app.setStyleSheet(_qss(colors))
    _current_mode = mode
    return mode
