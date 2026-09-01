"""Integration smoke: host the real bundled web UI in QWebEngineView and verify the
QWebChannel bridge loads live data from a temp database.

Run with the venv Python on a graphical platform (WebEngine may not render headless).
This is a positive smoke test: if the page fails to bind the bridge or render terms, it
fails loudly.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from cyberglossary.database import connection, migrations
from cyberglossary.database.repositories import (
    AliasRepository,
    CategoryRepository,
    ProfileRepository,
    SearchRepository,
    SectionRepository,
    SettingsRepository,
    TagRepository,
    TermRepository,
)
from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.services.search_service import SearchService
from cyberglossary.ui.web.bridge import Bridge


def _build_services(conn):
    ps = ProfileService(ProfileRepository(conn), SettingsRepository(conn))
    glossary = GlossaryService(
        ProfileRepository(conn),
        TermRepository(conn),
        SectionRepository(conn),
        AliasRepository(conn),
        CategoryRepository(conn),
        TagRepository(conn),
    )
    search = SearchService(SearchRepository(conn))
    return ps, glossary, search


def test_web_ui_renders_live_data(qapp):
    web_dir = Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"
    with tempfile.TemporaryDirectory() as tmp:
        conn = connection.connect(os.path.join(tmp, "t.db"))
        migrations.migrate(conn)
        ps, glossary, search = _build_services(conn)
        pid = ps.create_profile("CRTO").id
        cat = glossary.create_category(pid, "Auth")
        t = glossary.create_term(pid, "LDAP", "Lightweight Directory Access Protocol")
        glossary.set_term_category(t.id, cat.id)
        glossary.add_alias(t.id, "LDPA")
        glossary.add_section(t.id, "Ports", "389")

        bridge = Bridge(
            ps,
            glossary,
            search,
            LookupService(lambda: None, ps, glossary, search),
            BackupService(conn, ":memory:"),
            settings_store=None,
            on_theme=lambda d: None,
            on_file_action=lambda k: None,
            on_change_hotkey=lambda: None,
            on_capture_changed=lambda o: None,
            on_exit=lambda: None,
            get_hotkey_text=lambda: "Ctrl+Shift+K",
        )

        view = QWebEngineView()
        channel = QWebChannel(view.page())
        channel.registerObject("bridge", bridge)
        view.page().setWebChannel(channel)

        outcome = {"ok": False, "error": "timeout", "phase": 0}

        def probe_initial():
            view.page().runJavaScript(
                "JSON.stringify({loaded: !!window.__loaded, jserr: window.__jserr||null, "
                "termsLen: window.__state ? window.__state.terms.length : -1, "
                "listText: (document.getElementById('listCount')||{}).textContent||''})",
                finish_initial,
            )

        def finish_initial(out):
            try:
                data = json.loads(out)
                outcome["loaded"] = data.get("loaded")
                outcome["error"] = data.get("jserr")
                if data.get("loaded") and data.get("termsLen") == 1 and data.get("listText") == "(1)":
                    outcome["phase"] = 1
                    # Mutate through the bridge; dataChanged must refresh the rendered list.
                    bridge.createTerm("Kerberos", "", "")
                    QTimer.singleShot(800, probe_after_mutation)
                else:
                    outcome["ok"] = False
                    QTimer.singleShot(200, qapp.quit)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = str(exc)
                QTimer.singleShot(200, qapp.quit)

        def probe_after_mutation():
            view.page().runJavaScript(
                "JSON.stringify({listText: (document.getElementById('listCount')||{}).textContent||'', "
                "termsLen: window.__state ? window.__state.terms.length : -1, "
                "hasImport: !!document.getElementById('btnImport'), "
                "hasExport: !!document.getElementById('btnExport'), "
                "hasFileMenuGone: !document.getElementById('btnFileMenu'), "
                "hasHotkeyChange: !!document.getElementById('btnHotkeyChange'), "
                "languageGone: !document.getElementById('setLanguage'), "
                "themeRowGone: !document.getElementById('setThemeSwitch')})",
                finish_after,
            )

        def finish_after(out):
            try:
                data = json.loads(out)
                outcome["phase"] = 2
                outcome["termsLen"] = data.get("termsLen")
                outcome["listText"] = data.get("listText")
                outcome["ok"] = bool(
                    data.get("termsLen") == 2
                    and data.get("listText") == "(2)"
                    and data.get("hasImport") and data.get("hasExport")
                    and data.get("hasFileMenuGone")
                    and data.get("hasHotkeyChange") and data.get("languageGone")
                    and data.get("themeRowGone")
                )
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = str(exc)
            QTimer.singleShot(200, qapp.quit)

        view.loadFinished.connect(lambda ok: QTimer.singleShot(2000, probe_initial))
        view.load(QUrl.fromLocalFile(str(web_dir / "index.html")))
        qapp.setQuitOnLastWindowClosed(False)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(qapp.quit)
        timer.start(15000)
        qapp.exec()
        conn.close()

    assert outcome["ok"], f"web UI failed the integration flow: {outcome}"
