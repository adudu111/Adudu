"""QWebChannel bridge: clean JS <-> Python communication for the web UI.

Every slot and signal here is the ONLY channel between the embedded HTML/JS and the
backend. The JavaScript layer never touches SQLite, repositories, or services directly —
it calls these methods and receives plain-JSON payloads.

The services are entirely unchanged; this module merely adapts their existing API to a
serializable, UI-friendly contract and re-emits ``dataChanged`` after any mutation so the
frontend can re-render. Backend/domain errors are converted to user-facing ``toast``
notifications — never swallowed silently and never leaked as tracebacks.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict

from PySide6.QtCore import QObject, Signal, Slot

from cyberglossary.database.models import Alias, Category, Section, Term
from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.services.search_service import SearchResult, SearchService


def _term_dict(term: Term, category: Category | None, aliases: list[Alias], sections: list[Section]) -> dict:
    return {
        "id": term.id,
        "name": term.term,
        "full_name": term.full_name,
        "category": category.name if category else None,
        "aliases": [a.alias for a in aliases],
        "sections": [
            {"id": s.id, "title": s.title, "content": s.content, "sort_order": s.sort_order}
            for s in sections
        ],
    }


class Bridge(QObject):
    """The single JS<->Python surface. Instantiate once per app session."""

    dataChanged = Signal()          # any mutation happened -> frontend re-renders
    lookupResult = Signal(str)      # JSON-encoded LookupResult -> render the popup
    hotkeyChanged = Signal(str)     # human-readable hotkey text changed
    themeChanged = Signal(str)      # "dark" | "light"
    openSettings = Signal()         # open the in-app settings dialog
    openTermInWindow = Signal(int, bool)  # (term_id, edit_mode) -> main window
    openCreateTerm = Signal(str)    # term name -> open the New Term dialog in main window
    toast = Signal(str)

    def __init__(
        self,
        profile_service: ProfileService,
        glossary_service: GlossaryService,
        search_service: SearchService,
        lookup_service: LookupService,
        backup_service: BackupService,
        settings_store,
        on_theme: Callable[[bool], None],
        on_file_action: Callable[[str], None],
        on_change_hotkey: Callable[[], None],
        on_capture_changed: Callable[[bool], None],
        on_exit: Callable[[], None],
        get_hotkey_text: Callable[[], str],
        on_ready: Callable[[], None] | None = None,
        on_close_popup: Callable[[], None] | None = None,
        on_open_term: Callable[[int, bool], None] | None = None,
        on_start_move: Callable[[], None] | None = None,
        on_start_resize: Callable[[str], None] | None = None,
        on_request_create_term: Callable[[str], None] | None = None,
        on_copy_text: Callable[[str], None] | None = None,
        on_launcher_move: Callable[[], None] | None = None,
        on_launcher_resize: Callable[[str], None] | None = None,
        on_launcher_minimize: Callable[[], None] | None = None,
        on_launcher_restore: Callable[[], None] | None = None,
        on_launcher_close: Callable[[], None] | None = None,
        on_launcher_recent: Callable[[int], None] | None = None,
        on_launcher_pin: Callable[[int], None] | None = None,
        on_change_launcher_hotkey: Callable[[], None] | None = None,
        get_launcher_hotkey_text: Callable[[], str] | None = None,
        get_third_party_notices: Callable[[], str] | None = None,
        on_create_term_move: Callable[[], None] | None = None,
        on_create_term_resize: Callable[[str], None] | None = None,
        on_create_term_close: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._profiles = profile_service
        self._glossary = glossary_service
        self._search = search_service
        self._lookup = lookup_service
        self._backup = backup_service
        self._settings_store = settings_store
        self._on_theme = on_theme
        self._on_file_action = on_file_action
        self._on_change_hotkey = on_change_hotkey
        self._on_capture_changed = on_capture_changed
        self._on_exit = on_exit
        self._get_hotkey_text = get_hotkey_text
        self._on_ready = on_ready
        self._on_close_popup = on_close_popup
        self._on_open_term = on_open_term
        self._on_start_move = on_start_move
        self._on_start_resize = on_start_resize
        self._on_request_create_term = on_request_create_term
        self._on_copy_text = on_copy_text
        self._on_launcher_move = on_launcher_move
        self._on_launcher_resize = on_launcher_resize
        self._on_launcher_minimize = on_launcher_minimize
        self._on_launcher_restore = on_launcher_restore
        self._on_launcher_close = on_launcher_close
        self._on_launcher_recent = on_launcher_recent
        self._on_launcher_pin = on_launcher_pin
        self._on_change_launcher_hotkey = on_change_launcher_hotkey
        self._get_launcher_hotkey_text = get_launcher_hotkey_text
        self._get_third_party_notices = get_third_party_notices
        self._on_create_term_move = on_create_term_move
        self._on_create_term_resize = on_create_term_resize
        self._on_create_term_close = on_create_term_close
        self._pending_create_name = ""

    # --- frontend readiness -------------------------------------------------

    @Slot()
    def frontendReady(self) -> None:
        """Signalled by the JS once QWebChannel is connected and ready to receive."""
        if self._on_ready is not None:
            self._on_ready()

    # --- lookup popup hand-off ----------------------------------------------

    @Slot()
    def closePopup(self) -> None:
        if self._on_close_popup is not None:
            self._on_close_popup()

    @Slot(int, bool)
    def openTerm(self, term_id: int, edit_mode: bool) -> None:
        if self._on_open_term is not None:
            self._on_open_term(term_id, edit_mode)

    @Slot()
    def startMove(self) -> None:
        if self._on_start_move is not None:
            self._on_start_move()

    @Slot(str)
    def startResize(self, edge: str) -> None:
        if self._on_start_resize is not None:
            self._on_start_resize(edge)

    @Slot(str)
    def requestCreateTerm(self, name: str) -> None:
        if self._on_request_create_term is not None:
            self._on_request_create_term(name)

    # --- launcher (global search) ------------------------------------------

    @Slot(str)
    def copyText(self, text: str) -> None:
        if self._on_copy_text is not None:
            self._on_copy_text(text)

    @Slot()
    def launcherMove(self) -> None:
        if self._on_launcher_move is not None:
            self._on_launcher_move()

    @Slot(str)
    def launcherResize(self, edge: str) -> None:
        if self._on_launcher_resize is not None:
            self._on_launcher_resize(edge)

    @Slot()
    def launcherMinimize(self) -> None:
        if self._on_launcher_minimize is not None:
            self._on_launcher_minimize()

    @Slot()
    def launcherRestore(self) -> None:
        if self._on_launcher_restore is not None:
            self._on_launcher_restore()

    @Slot()
    def launcherClose(self) -> None:
        if self._on_launcher_close is not None:
            self._on_launcher_close()

    @Slot(int)
    def launcherAddRecent(self, term_id: int) -> None:
        if self._on_launcher_recent is not None:
            self._on_launcher_recent(term_id)

    @Slot(int)
    def launcherTogglePin(self, term_id: int) -> None:
        if self._on_launcher_pin is not None:
            self._on_launcher_pin(term_id)

    @Slot(result=str)
    def launcherInit(self) -> str:
        recent_ids = self._settings_store.launcher_recent if self._settings_store else []
        pinned_ids = self._settings_store.launcher_pinned if self._settings_store else []
        recent: list[dict] = []
        pinned: list[dict] = []
        for term_id in recent_ids:
            term = self._glossary.get_term(term_id)
            if term is not None:
                recent.append(self._term_dict(term))
        for term_id in pinned_ids:
            term = self._glossary.get_term(term_id)
            if term is not None:
                pinned.append(self._term_dict(term))
        return json.dumps({"recent": recent, "pinned": pinned})

    # --- create-term window -------------------------------------------------

    @Slot(str)
    def setCreateTermName(self, name: str) -> None:
        self._pending_create_name = name

    @Slot(str)
    def openCreateTermWindow(self, name: str) -> None:
        if self._on_request_create_term is not None:
            self._on_request_create_term(name)

    @Slot(result=str)
    def getCreateTermInit(self) -> str:
        pid = self._pid()
        categories = self._glossary.list_categories(pid) if pid is not None else []
        return json.dumps(
            {
                "name": self._pending_create_name or "",
                "categories": [c.name for c in categories],
            }
        )

    @Slot()
    def createTermMove(self) -> None:
        if self._on_create_term_move is not None:
            self._on_create_term_move()

    @Slot(str)
    def createTermResize(self, edge: str) -> None:
        if self._on_create_term_resize is not None:
            self._on_create_term_resize(edge)

    @Slot()
    def createTermClose(self) -> None:
        if self._on_create_term_close is not None:
            self._on_create_term_close()

    # --- helpers ----------------------------------------------------------

    @contextmanager
    def _errors(self) -> Iterator[None]:
        """Convert service errors into user-facing toasts; keep the JS callback alive."""
        try:
            yield
        except Exception as exc:  # noqa: BLE001 - UI boundary: friendly message only
            self.toast.emit(str(exc))

    def _pid(self) -> int | None:
        return self._profiles.get_active_profile_id()

    # --- profiles ---------------------------------------------------------

    @Slot(result=str)
    def getInitData(self) -> str:
        """Return everything the initial render needs, as a JSON string."""
        return json.dumps(
            {
                "profiles": [asdict(p) for p in self._profiles.list_profiles()],
                "active_profile_id": self._pid(),
                "categories": [asdict(c) for c in self._glossary.list_categories(self._pid())] if self._pid() else [],
                "terms": self._all_terms(),
                "settings": self._settings_dict(),
                "hotkey": self._get_hotkey_text(),
            }
        )

    def _all_terms(self) -> list[dict]:
        pid = self._pid()
        if pid is None:
            return []
        return [
            self._term_dict(t)
            for t in self._glossary.list_terms(pid)
        ]

    def _term_dict(self, term: Term) -> dict:
        return _term_dict(
            term,
            self._glossary.get_term_category(term.id),
            self._glossary.list_aliases(term.id),
            self._glossary.list_sections(term.id),
        )

    def _settings_dict(self) -> dict:
        s = self._settings_store
        if s is None:
            return {
                "theme": "dark",
                "lookup_paused": False,
                "hotkey_modifiers": 6,
                "hotkey_key": 68,
            }
        return {
            "theme": s.theme,
            "lookup_paused": s.lookup_paused,
            "hotkey_modifiers": s.hotkey_modifiers,
            "hotkey_key": s.hotkey_key,
        }

    @Slot(result=str)
    def getProfiles(self) -> str:
        return json.dumps(
            {
                "profiles": [asdict(p) for p in self._profiles.list_profiles()],
                "active_profile_id": self._pid(),
            }
        )

    @Slot(int, result=str)
    def getProfile(self, profile_id: int) -> str:
        profile = self._profiles.get_profile(profile_id)
        if profile is None:
            return "null"
        return json.dumps(asdict(profile))

    @Slot(int)
    def setActiveProfile(self, profile_id: int) -> None:
        with self._errors():
            self._profiles.set_active_profile(profile_id)
            self.dataChanged.emit()

    @Slot(str, str, result=str)
    def createProfile(self, name: str, desc: str = "") -> str:
        with self._errors():
            profile = self._profiles.create_profile(name, desc or "")
            self.dataChanged.emit()
            return json.dumps(asdict(profile))
        return "null"

    @Slot(int, str, result=str)
    def renameProfile(self, profile_id: int, name: str) -> str:
        with self._errors():
            profile = self._profiles.rename_profile(profile_id, name)
            self.dataChanged.emit()
            return json.dumps(asdict(profile))
        return "null"

    @Slot(int, result=bool)
    def deleteProfile(self, profile_id: int) -> bool:
        with self._errors():
            self._profiles.delete_profile(profile_id)
            self.dataChanged.emit()
            return True
        return False

    # --- terms ------------------------------------------------------------

    @Slot(result=str)
    def getTerms(self) -> str:
        pid = self._pid()
        terms = self._glossary.list_terms(pid) if pid is not None else []
        data = [self._term_dict(t) for t in terms]
        return json.dumps(data)

    @Slot(int, result=str)
    def getTerm(self, term_id: int) -> str:
        term = self._glossary.get_term(term_id)
        if term is None:
            return "null"
        return json.dumps(self._term_dict(term))

    @Slot(str, str, str, result=str)
    def createTerm(self, name: str, full_name: str, category: str) -> str:
        pid = self._pid()
        if pid is None:
            return "null"
        with self._errors():
            term = self._glossary.create_term(pid, name, full_name)
            category_id = self._category_id(category)
            if category_id is not None:
                term = self._glossary.set_term_category(term.id, category_id)
            self.dataChanged.emit()
            return json.dumps(self._term_dict(term))
        return "null"

    @Slot(int, str, str, str, result=str)
    def updateTerm(self, term_id: int, name: str, full_name: str, category: str) -> str:
        with self._errors():
            if name:
                self._glossary.rename_term(term_id, name)
            self._glossary.set_full_name(term_id, full_name)
            self._glossary.set_term_category(term_id, self._category_id(category))
            self.dataChanged.emit()
            term = self._glossary.get_term(term_id)
            return json.dumps(self._term_dict(term))
        return "null"

    @Slot(int, result=bool)
    def deleteTerm(self, term_id: int) -> bool:
        with self._errors():
            self._glossary.delete_term(term_id)
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, result=str)
    def duplicateTerm(self, term_id: int) -> str:
        with self._errors():
            term = self._glossary.duplicate_term(term_id)
            self.dataChanged.emit()
            return json.dumps(self._term_dict(term))
        return "null"

    @Slot(int, str, result=bool)
    def assignCategory(self, term_id: int, category: str) -> bool:
        with self._errors():
            self._glossary.set_term_category(term_id, self._category_id(category))
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, result=bool)
    def clearCategory(self, term_id: int) -> bool:
        with self._errors():
            self._glossary.set_term_category(term_id, None)
            self.dataChanged.emit()
            return True
        return False

    # --- aliases ----------------------------------------------------------

    @Slot(int, result=str)
    def getAliases(self, term_id: int) -> str:
        return json.dumps([a.alias for a in self._glossary.list_aliases(term_id)])

    @Slot(int, str, result=bool)
    def addAlias(self, term_id: int, alias: str) -> bool:
        with self._errors():
            self._glossary.add_alias(term_id, alias)
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, str, result=bool)
    def removeAlias(self, term_id: int, alias: str) -> bool:
        with self._errors():
            for a in self._glossary.list_aliases(term_id):
                if a.alias == alias:
                    self._glossary.delete_alias(a.id)
            self.dataChanged.emit()
            return True
        return False

    # --- sections ---------------------------------------------------------

    @Slot(int, result=str)
    def getSections(self, term_id: int) -> str:
        return json.dumps([asdict(s) for s in self._glossary.list_sections(term_id)])

    @Slot(int, str, result=str)
    @Slot(int, str, str, result=str)
    def addSection(self, term_id: int, title: str, content: str = "") -> str:
        with self._errors():
            section = self._glossary.add_section(term_id, title, content)
            self.dataChanged.emit()
            return json.dumps(asdict(section))
        return "null"

    @Slot(int, str, result=bool)
    def updateSection(self, section_id: int, content: str) -> bool:
        with self._errors():
            self._glossary.set_section_content(section_id, content)
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, str, result=bool)
    def renameSection(self, section_id: int, title: str) -> bool:
        with self._errors():
            self._glossary.rename_section(section_id, title)
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, result=bool)
    def deleteSection(self, section_id: int) -> bool:
        with self._errors():
            self._glossary.delete_section(section_id)
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, str, result=bool)
    def reorderSections(self, term_id: int, ordered_ids_json: str) -> bool:
        with self._errors():
            ordered = json.loads(ordered_ids_json)
            self._glossary.reorder_sections(term_id, ordered)
            self.dataChanged.emit()
            return True
        return False

    # --- categories -------------------------------------------------------

    @Slot(result=str)
    def getCategories(self) -> str:
        pid = self._pid()
        if pid is None:
            return "[]"
        return json.dumps([asdict(c) for c in self._glossary.list_categories(pid)])

    @Slot(str, result=str)
    def createCategory(self, name: str) -> str:
        pid = self._pid()
        if pid is None:
            return "null"
        with self._errors():
            cat = self._glossary.create_category(pid, name)
            self.dataChanged.emit()
            return json.dumps(asdict(cat))
        return "null"

    @Slot(int, str, result=bool)
    def renameCategory(self, category_id: int, name: str) -> bool:
        with self._errors():
            self._glossary.rename_category(category_id, name)
            self.dataChanged.emit()
            return True
        return False

    @Slot(int, result=bool)
    def deleteCategory(self, category_id: int) -> bool:
        with self._errors():
            self._glossary.delete_category(category_id)
            self.dataChanged.emit()
            return True
        return False

    @Slot(str, result=bool)
    def reorderCategories(self, ordered_ids_json: str) -> bool:
        pid = self._pid()
        if pid is None:
            return False
        with self._errors():
            self._glossary.reorder_categories(pid, json.loads(ordered_ids_json))
            self.dataChanged.emit()
            return True
        return False

    def _category_id(self, name: str | None) -> int | None:
        if not name:
            return None
        pid = self._pid()
        if pid is None:
            return None
        for c in self._glossary.list_categories(pid):
            if c.name == name:
                return c.id
        return None

    # --- search / lookup --------------------------------------------------

    @Slot(str, result=str)
    def search(self, query: str) -> str:
        results = self._search.search(query, self._pid())
        return json.dumps([_search_result(r) for r in results])

    @Slot(str, result=str)
    def searchTerms(self, query: str) -> str:
        """Canonical search method for the global search box (FTS5)."""
        return self.search(query)

    @Slot(str, result=str)
    def launcherSearch(self, query: str) -> str:
        """Grouped search for the launcher: matching categories first, then terms inside."""
        results = self._search.search(query, self._pid())
        groups: dict[str, list[dict]] = {}
        order: list[str] = []
        for r in results:
            category = r.category or "Uncategorized"
            if category not in groups:
                groups[category] = []
                order.append(category)
            groups[category].append(_search_result(r))
        ql = query.strip().lower()
        order.sort(key=lambda c: (0 if ql and c.lower().find(ql) >= 0 else 1, c.lower()))
        return json.dumps(
            {
                "groups": [{"category": c, "terms": groups[c]} for c in order],
                "count": len(results),
            }
        )

    @Slot(str, result=str)
    def lookup(self, text: str) -> str:
        result = self._lookup.lookup(text)
        return json.dumps(_lookup_dict(result))

    # --- settings / theme -------------------------------------------------

    @Slot(result=str)
    def getSettings(self) -> str:
        return json.dumps(self._settings_dict())

    @Slot(bool)
    def setTheme(self, dark: bool) -> None:
        self._on_theme(dark)
        self.themeChanged.emit("dark" if dark else "light")

    @Slot(result=str)
    def getHotkeyText(self) -> str:
        return self._get_hotkey_text()

    @Slot()
    def changeHotkey(self) -> None:
        self._on_change_hotkey()
        self.hotkeyChanged.emit(self._get_hotkey_text())

    @Slot()
    def changeLauncherHotkey(self) -> None:
        if self._on_change_launcher_hotkey is not None:
            self._on_change_launcher_hotkey()

    @Slot(result=str)
    def getLauncherHotkeyText(self) -> str:
        if self._get_launcher_hotkey_text is not None:
            return self._get_launcher_hotkey_text()
        return ""

    @Slot(result=str)
    def getThirdPartyNotices(self) -> str:
        if self._get_third_party_notices is not None:
            return self._get_third_party_notices()
        return "Third-party notices are not available."

    @Slot(bool)
    def setCapture(self, on: bool) -> None:
        self._on_capture_changed(on)

    # --- file / data actions (delegate to native handlers) ----------------

    @Slot(str)
    def fileAction(self, key: str) -> None:
        self._on_file_action(key)

    @Slot()
    def exitApp(self) -> None:
        self._on_exit()


def _search_result(r: SearchResult) -> dict:
    return {
        "term_id": r.term_id,
        "term": r.term,
        "full_name": r.full_name,
        "category": r.category,
        "snippet": r.snippet,
    }


def _lookup_dict(r) -> dict:
    return {
        "found": r.found,
        "query": r.query,
        "term_id": r.term_id,
        "term": r.term,
        "full_name": r.full_name,
        "category": r.category,
        "sections": [
            {"id": s.id, "title": s.title, "content": s.content, "sort_order": s.sort_order}
            for s in r.sections
        ],
        "profile_name": r.profile_name,
    }
