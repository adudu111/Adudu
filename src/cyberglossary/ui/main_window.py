"""Main application window: menu bar + header + sidebar + stacked content."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cyberglossary import APP_NAME, __version__
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.services.search_service import SearchService
from cyberglossary.ui import theme
from cyberglossary.ui.categories_page import CategoriesPage
from cyberglossary.ui.icons import (
    command_icon,
    folder_icon,
    list_icon,
    moon_icon,
    search,
    sidebar_icon,
    sliders_icon,
    sun_icon,
)
from cyberglossary.ui.profile_selector import ProfileSelector
from cyberglossary.ui.term_editor import TermEditor
from cyberglossary.ui.term_list import TermList


class MainWindow(QMainWindow):
    export_json_requested = Signal()
    export_markdown_requested = Signal()
    import_json_requested = Signal()
    backup_requested = Signal()
    restore_requested = Signal()
    settings_requested = Signal()
    lookup_requested = Signal()
    global_search_changed = Signal(str)
    global_search_focused = Signal()

    def __init__(
        self,
        profile_service: ProfileService,
        glossary_service: GlossaryService,
        search_service: SearchService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1024, 640)
        self._theme = theme.DARK
        self._exiting = False
        self._sidebar_collapsed = False

        self._profile_service = profile_service
        self._glossary_service = glossary_service

        self.profile_selector = ProfileSelector(profile_service)
        self.term_list = TermList(glossary_service, search_service)
        self.term_editor = TermEditor(glossary_service)
        self.categories_page = CategoriesPage(glossary_service, profile_service)

        self._build_stack()

        central = QWidget()
        central.setObjectName("app")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_header())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.sidebar = self._build_sidebar()
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stack, 1)
        central_layout.addWidget(body, 1)

        self.setCentralWidget(central)

        self._wire_signals()
        self._build_menu()
        self._build_shortcuts()

        active = profile_service.get_active_profile()
        if active is not None:
            self.term_list.set_profile(active.id)

    # --- header / sidebar / stack -----------------------------------------

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(52)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        rail_btn = QPushButton()
        rail_btn.setIcon(sidebar_icon())
        rail_btn.setObjectName("ghost")
        rail_btn.setFixedSize(28, 28)
        rail_btn.setToolTip("Toggle sidebar · Ctrl+B")
        rail_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(rail_btn)

        self._crumb_root = QLabel("Glossary")
        self._crumb_root.setObjectName("crumbRoot")
        layout.addWidget(self._crumb_root)

        self._crumb_sep = QLabel("\u203a")
        self._crumb_sep.setObjectName("crumbSep")
        layout.addWidget(self._crumb_sep)

        self.page_title = QLabel("All Terms")
        self.page_title.setObjectName("pageTitle")
        layout.addWidget(self.page_title)

        self._preview_tag = QLabel("Design preview")
        self._preview_tag.setObjectName("previewTag")
        layout.addWidget(self._preview_tag)

        layout.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("search")
        self.search_edit.setPlaceholderText("Search terms\u2026")
        self.search_edit.setMinimumWidth(320)
        self.search_edit.setMaximumWidth(420)
        self.search_edit.setFixedHeight(32)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(search(), QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        hint = QLabel("Ctrl K")
        hint.setObjectName("kbdChip")
        layout.addWidget(hint)

        lookup_btn = QPushButton()
        lookup_btn.setIcon(command_icon())
        lookup_btn.setObjectName("ghost")
        lookup_btn.setFixedSize(28, 28)
        lookup_btn.setToolTip("Lookup popup · global hotkey")
        lookup_btn.clicked.connect(self.lookup_requested.emit)
        layout.addWidget(lookup_btn)
        return header

    def _focus_search(self) -> None:
        self._show_terms()
        self.search_edit.setFocus()
        self.search_edit.selectAll()
        self.global_search_focused.emit()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(270)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)

        # Brand block (§14): gradient tile + name + tagline + version.
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        self.brand_tile = QLabel("A")
        self.brand_tile.setObjectName("brandTile")
        self.brand_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_tile.setFixedSize(28, 28)
        brand_row.addWidget(self.brand_tile)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        self.brand_name = QLabel(APP_NAME)
        self.brand_name.setObjectName("brandName")
        brand_text.addWidget(self.brand_name)
        self.brand_tagline = QLabel("Cyber Glossary")
        self.brand_tagline.setObjectName("brandVersion")
        brand_text.addWidget(self.brand_tagline)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)
        layout.addSpacing(8)

        # PROFILE section.
        self.profile_section_label = QLabel("PROFILE")
        self.profile_section_label.setObjectName("sectionLabel")
        layout.addWidget(self.profile_section_label)
        layout.addWidget(self.profile_selector)

        layout.addSpacing(8)

        # LIBRARY section.
        self.library_section_label = QLabel("LIBRARY")
        self.library_section_label.setObjectName("sectionLabel")
        layout.addWidget(self.library_section_label)

        self.terms_btn = self._nav_button("Terms", self._show_terms, list_icon(), checked=True)
        self.categories_btn = self._nav_button("Categories", self._show_categories, folder_icon())
        layout.addWidget(self.terms_btn)
        layout.addWidget(self.categories_btn)

        layout.addSpacing(8)

        # SYSTEM section.
        self.system_section_label = QLabel("SYSTEM")
        self.system_section_label.setObjectName("sectionLabel")
        layout.addWidget(self.system_section_label)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(sliders_icon())
        self.settings_btn.setObjectName("nav")
        self.settings_btn.setCheckable(True)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        layout.addStretch(1)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("divider")
        layout.addWidget(divider)

        self.theme_btn = QPushButton("Dark / Light")
        self.theme_btn.setIcon(moon_icon())
        self.theme_btn.setObjectName("nav")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        # Bottom row: collapse rail toggle + version.
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        self.collapse_btn = QPushButton()
        self.collapse_btn.setIcon(sidebar_icon())
        self.collapse_btn.setObjectName("ghost")
        self.collapse_btn.setFixedSize(28, 28)
        self.collapse_btn.setToolTip("Collapse sidebar (Ctrl+B)")
        self.collapse_btn.clicked.connect(self._toggle_sidebar)
        bottom_row.addWidget(self.collapse_btn)
        bottom_row.addStretch(1)
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("brandVersion")
        bottom_row.addWidget(self.version_label)
        layout.addLayout(bottom_row)

        # Widgets hidden when the sidebar collapses to the 64px rail.
        self._sidebar_hideable = [
            self.brand_name,
            self.brand_tagline,
            self.profile_section_label,
            self.profile_selector,
            self.library_section_label,
            self.system_section_label,
            self.version_label,
        ]
        self._sidebar_buttons = [
            (self.terms_btn, "Terms"),
            (self.categories_btn, "Categories"),
            (self.settings_btn, "Settings"),
            (self.theme_btn, "Dark / Light"),
        ]
        return sidebar

    def _nav_button(self, text: str, handler, icon=None, checked: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("nav")
        if icon is not None:
            button.setIcon(icon)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setChecked(checked)
        button.clicked.connect(handler)
        return button

    def _build_stack(self) -> None:
        self.stack = QStackedWidget()

        self.terms_pane = QWidget()
        terms_layout = QHBoxLayout(self.terms_pane)
        terms_layout.setContentsMargins(0, 0, 0, 0)
        terms_split = QSplitter(Qt.Orientation.Horizontal)
        terms_split.addWidget(self.term_list)
        terms_split.addWidget(self.term_editor)
        terms_split.setStretchFactor(0, 0)
        terms_split.setStretchFactor(1, 1)
        terms_split.setSizes([320, 1100])
        self.terms_split = terms_split
        terms_layout.addWidget(terms_split)
        self.stack.addWidget(self.terms_pane)

        self.stack.addWidget(self.categories_page)

    # --- menu --------------------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        import_json = file_menu.addAction("Import JSON \u2026")
        export_json = file_menu.addAction("Export JSON \u2026")
        export_markdown = file_menu.addAction("Export Markdown \u2026")
        file_menu.addSeparator()
        backup = file_menu.addAction("Backup Database \u2026")
        restore = file_menu.addAction("Restore Database \u2026")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        import_json.triggered.connect(self.import_json_requested.emit)
        export_json.triggered.connect(self.export_json_requested.emit)
        export_markdown.triggered.connect(self.export_markdown_requested.emit)
        backup.triggered.connect(self.backup_requested.emit)
        restore.triggered.connect(self.restore_requested.emit)
        exit_action.triggered.connect(self.exit_application)

    # --- shortcuts (§25) ---------------------------------------------------

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._new_term_shortcut)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_filter_shortcut)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._edit_shortcut)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self._toggle_sidebar)
        QShortcut(QKeySequence("F"), self, activated=self._toggle_term_list)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self._show_terms)
        QShortcut(QKeySequence("Ctrl+2"), self, activated=self._show_categories)
        QShortcut(QKeySequence("Ctrl+3"), self, activated=self.settings_requested.emit)

    def _new_term_shortcut(self) -> None:
        self._show_terms()
        self.term_list.new_btn.click()

    def _focus_filter_shortcut(self) -> None:
        self._show_terms()
        self.term_list._focus_filter()

    def _edit_shortcut(self) -> None:
        self._show_terms()
        self.term_editor.enter_edit_mode()

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        if self._sidebar_collapsed:
            self.sidebar.setMinimumWidth(64)
            self.sidebar.setMaximumWidth(64)
        else:
            self.sidebar.setMinimumWidth(250)
            self.sidebar.setMaximumWidth(270)
        for widget in self._sidebar_hideable:
            widget.setVisible(not self._sidebar_collapsed)
        for button, text in self._sidebar_buttons:
            button.setText("" if self._sidebar_collapsed else text)

    def _toggle_term_list(self) -> None:
        self._show_terms()
        self.term_list.setVisible(not self.term_list.isVisible())

    # --- navigation --------------------------------------------------------

    def _show_terms(self) -> None:
        self.page_title.setText("All Terms")
        self.stack.setCurrentWidget(self.terms_pane)

    def _show_categories(self) -> None:
        self.page_title.setText("Categories")
        self.categories_page.reload()
        self.stack.setCurrentWidget(self.categories_page)

    def _on_search_changed(self, text: str) -> None:
        self._show_terms()
        self.global_search_changed.emit(text)

    # --- signals -----------------------------------------------------------

    def _wire_signals(self) -> None:
        self.profile_selector.profile_selected.connect(self._on_profile_selected)
        self.term_list.term_selected.connect(self.term_editor.set_term)
        self.term_list.multi_selected.connect(self.term_editor.show_multi_selection)
        self.term_editor.term_deleted.connect(self._on_term_deleted)
        self.term_editor.term_duplicated.connect(self._on_term_duplicated)
        self.term_editor.term_renamed.connect(self._on_term_renamed)
        self.categories_page.term_selected.connect(self._on_category_term_selected)

    def _on_profile_selected(self, profile_id: object) -> None:
        self.select_profile(profile_id)

    def select_profile(self, profile_id: object) -> None:
        self.term_list.set_profile(profile_id)
        self.term_editor.set_term(None)
        self.profile_selector.refresh()
        if self.stack.currentWidget() is self.categories_page:
            self.categories_page.reload()

    def _on_term_deleted(self) -> None:
        self.term_list.refresh()
        self.term_editor.set_term(None)

    def _on_term_duplicated(self, new_id: int) -> None:
        self.term_list.refresh()
        self.term_list.select(new_id)

    def _on_term_renamed(self, term_id: int) -> None:
        self.term_list.refresh()
        self.term_list.select(term_id)

    def _on_category_term_selected(self, term_id: int) -> None:
        self._show_terms()
        self.term_list.refresh()
        self.term_list.select(term_id)

    # --- theme / lifecycle -------------------------------------------------

    def _toggle_theme(self) -> None:
        self.set_theme(theme.LIGHT if self._theme == theme.DARK else theme.DARK)

    def set_theme(self, mode: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._theme = mode
        theme.apply_theme(app, mode)
        self.theme_btn.setIcon(moon_icon() if mode == theme.DARK else sun_icon())

    def is_exiting(self) -> bool:
        return self._exiting

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._exiting:
            event.accept()
            return
        event.ignore()
        self.hide()

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def exit_application(self) -> None:
        self._exiting = True
        self.close()
