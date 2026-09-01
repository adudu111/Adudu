"""Integration smoke for the launcher page (expanded term content + pin result).

Hosts ``launcher.html`` in a QWebEngineView with the shared Bridge, then drives a search,
expands a term, and asserts its section content renders (which exercises the term-id
normalization so getTerm loads correctly). This is a positive smoke test.
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

from cyberglossary.config.settings import AppSettings
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


def test_launcher_expands_term_content(qapp):
    web_dir = Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"
    with tempfile.TemporaryDirectory() as tmp:
        conn = connection.connect(os.path.join(tmp, "t.db"))
        migrations.migrate(conn)
        ps, glossary, search = _build_services(conn)
        pid = ps.create_profile("CRTO").id
        cat = glossary.create_category(pid, "CMD")
        term = glossary.create_term(pid, "klist", "View cached Kerberos tickets")
        glossary.set_term_category(term.id, cat.id)
        glossary.add_section(term.id, "Purpose", "List the cached Kerberos tickets")

        bridge = Bridge(
            ps,
            glossary,
            search,
            LookupService(lambda: None, ps, glossary, search),
            BackupService(conn, ":memory:"),
            settings_store=AppSettings(),
            on_theme=lambda d: None,
            on_file_action=lambda k: None,
            on_change_hotkey=lambda: None,
            on_capture_changed=lambda o: None,
            on_exit=lambda: None,
            get_hotkey_text=lambda: "Ctrl+Shift+D",
            on_copy_text=lambda t: None,
            on_launcher_recent=lambda i: None,
            on_launcher_pin=lambda i: None,
        )

        view = QWebEngineView()
        channel = QWebChannel(view.page())
        channel.registerObject("bridge", bridge)
        view.page().setWebChannel(channel)

        outcome = {"ok": False, "error": "timeout", "tries": 0}
        term_id = term.id
        expected = "List the cached Kerberos tickets"

        def poll():
            outcome["tries"] += 1
            if outcome["tries"] > 40:
                outcome["error"] = "timeout waiting for content"
                QTimer.singleShot(200, qapp.quit)
                return
            view.page().runJavaScript(
                "var q=document.getElementById('q');"
                "if(q && q.value===''){q.value='klist';q.dispatchEvent(new Event('input'));}"
                f"var r=document.querySelector('.l-term[data-id=\"{term_id}\"]');"
                "if(r){var row=r.querySelector('[data-toggle]');row.click();}"
                "var body=r?r.querySelector('[data-body]'):null;"
                "JSON.stringify({found:!!r,content:(body?body.textContent:'')})",
                lambda out: _check(out),
            )

        def _check(out):
            try:
                data = json.loads(out)
                if data.get("found") and expected in data.get("content", ""):
                    outcome["ok"] = True
                    outcome["error"] = ""
                    QTimer.singleShot(200, qapp.quit)
                    return
                QTimer.singleShot(400, poll)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = str(exc)
                QTimer.singleShot(200, qapp.quit)

        view.loadFinished.connect(lambda ok: QTimer.singleShot(1500, poll))
        view.load(QUrl.fromLocalFile(str(web_dir / "launcher.html")))
        qapp.setQuitOnLastWindowClosed(False)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(qapp.quit)
        timer.start(25000)
        qapp.exec()
        conn.close()

    assert outcome["ok"], f"launcher failed the integration flow: {outcome}"
