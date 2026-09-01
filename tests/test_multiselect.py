"""Multi-select toggle behavior: un-checking one term must not clear the whole group."""

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


def test_multiselect_uncheck_keeps_other_terms(qapp):
    web_dir = Path(__file__).resolve().parent.parent / "src" / "cyberglossary" / "ui" / "web"
    with tempfile.TemporaryDirectory() as tmp:
        conn = connection.connect(os.path.join(tmp, "t.db"))
        migrations.migrate(conn)
        ps, glossary, search = _build_services(conn)
        pid = ps.create_profile("CRTO").id
        ps.set_active_profile(pid)
        for name in ("LDAP", "klist", "whoami"):
            glossary.create_term(pid, name)

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

        outcome = {"ok": False, "error": "timeout", "tries": 0}

        def poll():
            outcome["tries"] += 1
            if outcome["tries"] > 40:
                outcome["error"] = "timeout"
                QTimer.singleShot(200, qapp.quit)
                return
            view.page().runJavaScript(
                "(function(){"
                "if(!window.__loaded) return 'wait';"
                "if(!window.__state || !window.__state.multi) return 'wait';"
                "var rows=function(){return document.querySelectorAll('#listBox .term-row');};"
                "if(rows().length<2) return 'wait';"
                "var id0=rows()[0].dataset.term, id1=rows()[1].dataset.term;"
                "var ctrl=function(){return new MouseEvent('click',{ctrlKey:true,bubbles:true});};"
                "rows()[0].dispatchEvent(ctrl());"
                "rows()[1].dispatchEvent(ctrl());"
                "var s1=window.__state.multi.size;"
                "rows()[0].dispatchEvent(new MouseEvent('click',{bubbles:true}));"
                "var s2=window.__state.multi.size;"
                "var has0=window.__state.multi.has(+id0), has1=window.__state.multi.has(+id1);"
                "return JSON.stringify({s1:s1,s2:s2,has0:has0,has1:has1});"
                "})()",
                lambda out: _check(out),
            )

        def _check(out):
            if out is None or out == "" or out == "wait" or out == '"wait"':
                QTimer.singleShot(400, poll)
                return
            try:
                data = json.loads(out)
                # After 2 Ctrl+clicks -> 2 selected. After a plain click on the first
                # selected term -> only the second term remains selected (not cleared).
                ok = data["s1"] == 2 and data["s2"] == 1 and data["has0"] is False and data["has1"] is True
                if ok:
                    outcome["ok"] = True
                    outcome["error"] = ""
                else:
                    outcome["error"] = f"unexpected selection: {data}"
                QTimer.singleShot(200, qapp.quit)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = str(exc)
                QTimer.singleShot(200, qapp.quit)

        view.loadFinished.connect(lambda ok: QTimer.singleShot(1500, poll))
        view.load(QUrl.fromLocalFile(str(web_dir / "index.html")))
        qapp.setQuitOnLastWindowClosed(False)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(qapp.quit)
        timer.start(25000)
        qapp.exec()
        conn.close()

    assert outcome["ok"], f"multiselect toggle failed: {outcome}"
