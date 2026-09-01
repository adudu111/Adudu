"""Phase 7: theme persistence and file-action routing through the bridge."""

from __future__ import annotations

from cyberglossary.config import settings as settings_mod
from cyberglossary.services.backup_service import BackupService
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.ui.web.bridge import Bridge


def test_theme_persists_through_bridge(profile_service, glossary_service, search_service, conn, tmp_path):
    settings_path = tmp_path / "settings.json"
    app_settings = settings_mod.load(settings_path)
    calls = {"theme": []}

    def on_theme(dark):
        app_settings.theme = "dark" if dark else "light"
        settings_mod.save(app_settings, settings_path)
        calls["theme"].append(dark)

    bridge = Bridge(
        profile_service, glossary_service, search_service,
        LookupService(lambda: None, profile_service, glossary_service, search_service),
        BackupService(conn, ":memory:"),
        settings_store=app_settings,
        on_theme=on_theme, on_file_action=lambda k: None,
        on_change_hotkey=lambda: None, on_capture_changed=lambda o: None,
        on_exit=lambda: None, get_hotkey_text=lambda: "Ctrl+Shift+K",
    )

    bridge.setTheme(False)
    assert calls["theme"] == [False]
    assert settings_mod.load(settings_path).theme == "light"

    bridge.setTheme(True)
    assert settings_mod.load(settings_path).theme == "dark"


def test_file_action_routes_all_handlers(profile_service, glossary_service, search_service, conn):
    calls = []
    bridge = Bridge(
        profile_service, glossary_service, search_service,
        LookupService(lambda: None, profile_service, glossary_service, search_service),
        BackupService(conn, ":memory:"),
        settings_store=None,
        on_theme=lambda d: None, on_file_action=calls.append,
        on_change_hotkey=lambda: None, on_capture_changed=lambda o: None,
        on_exit=lambda: None, get_hotkey_text=lambda: "Ctrl+Shift+K",
    )
    for key in ("import-json", "export-json", "export-md", "backup", "restore", "exit"):
        bridge.fileAction(key)
    assert calls == ["import-json", "export-json", "export-md", "backup", "restore", "exit"]
