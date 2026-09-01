"""Regression: editing + saving a term keeps its category. The edit dialog's category
``<select>`` must carry the term's current category as its value (a term with category
"cmd" must show "cmd", not an empty value that clears the category on save)."""

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


def test_edit_save_keeps_category(qapp):
    web_dir = Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"
    with tempfile.TemporaryDirectory() as tmp:
        conn = connection.connect(os.path.join(tmp, "t.db"))
        migrations.migrate(conn)
        ps, glossary, search = _build_services(conn)
        pid = ps.create_profile("CRTO").id
        ps.set_active_profile(pid)
        cat = glossary.create_category(pid, "cmd")
        term = glossary.create_term(pid, "ldapsearch", "LDAP search tool")
        glossary.set_term_category(term.id, cat.id)

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
            get_hotkey_text=lambda: "Ctrl+Shift+D",
        )

        view = QWebEngineView()
        channel = QWebChannel(view.page())
        channel.registerObject("bridge", bridge)
        view.page().setWebChannel(channel)

        outcome = {"ok": False, "error": "timeout", "stage": "wait", "tries": 0}

        def run_js(js, cb):
            view.page().runJavaScript(js, cb)

        def poll_select():
            run_js(
                "(function(){"
                "if(!window.__loaded) return 'wait';"
                "var rows=document.querySelectorAll('#listBox .term-row');"
                "if(rows.length<1) return 'wait';"
                "rows[0].dispatchEvent(new MouseEvent('click',{bubbles:true}));"
                "return 'selected';})()",
                lambda out: _after_select(out),
            )

        def _after_select(out):
            if out in (None, "", "wait", '"wait"'):
                QTimer.singleShot(400, poll_select)
                return
            QTimer.singleShot(300, lambda: run_js(
                "(function(){var b=document.getElementById('btnEdit');"
                "if(!b) return 'noEdit'; b.click(); return 'edit';})()",
                lambda out2: _after_edit(out2),
            ))

        def _after_edit(out2):
            if out2 in (None, "", "noEdit"):
                outcome["stage"] = "edit"
                QTimer.singleShot(400, poll_select)
                return
            QTimer.singleShot(300, lambda: run_js(
                "(function(){var s=document.getElementById('eCat');"
                "return JSON.stringify({ok:!!s,val:s?s.value:null});})()",
                lambda out3: _final(out3),
            ))

        def _final(out3):
            try:
                data = json.loads(out3)
                outcome["stage"] = "final"
                outcome["ok"] = data.get("ok") is True and data.get("val") == "cmd"
                if not outcome["ok"]:
                    outcome["error"] = "edit select value was not the category: " + repr(data)
                QTimer.singleShot(200, qapp.quit)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = str(exc)
                QTimer.singleShot(200, qapp.quit)

        view.loadFinished.connect(lambda ok: QTimer.singleShot(1500, poll_select))
        view.load(QUrl.fromLocalFile(str(web_dir / "index.html")))
        qapp.setQuitOnLastWindowClosed(False)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(qapp.quit)
        timer.start(25000)
        qapp.exec()
        conn.close()

    assert outcome["ok"], f"edit-save category regression: {outcome}"
