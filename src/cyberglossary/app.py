"""Composition root: builds the SQLite connection, services, and the web shell.

``adudu.exe -> QApplication -> services -> QWebEngineView (local HTML) + QWebChannel``.
The embedded HTML/JS talks to the backend only through :class:`Bridge`. All native
Python facilities (hotkey, clipboard, lookup, import/export, backup/restore, tray,
settings persistence) are preserved and surfaced to the UI through the bridge.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cyberglossary.config import paths
from cyberglossary.database import connection, migrations
from cyberglossary.database.repositories import (
    AliasRepository,
    CategoryRepository,
    ProfileRepository,
    SearchRepository,
    SectionRepository,
    SettingsRepository,
    TagRepository,
    TemplateRepository,
    TemplateSectionRepository,
    TermRepository,
)
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.services.search_service import SearchService
from cyberglossary.services.template_service import TemplateService


def build_services(db_path: str | None = None):
    """Create the connection + services (migrating if needed).

    Returns (connection, profile, glossary, template, search).
    """
    paths.ensure_dirs()
    conn = connection.connect(db_path or str(paths.database_path()))
    migrations.migrate(conn)
    return _build_services_from_conn(conn)


def _build_services_from_conn(conn):
    profiles = ProfileRepository(conn)
    profile_service = ProfileService(profiles, SettingsRepository(conn))
    glossary_service = GlossaryService(
        profiles,
        TermRepository(conn),
        SectionRepository(conn),
        AliasRepository(conn),
        CategoryRepository(conn),
        TagRepository(conn),
    )
    template_service = TemplateService(
        profiles,
        TemplateRepository(conn),
        TemplateSectionRepository(conn),
    )
    search_service = SearchService(SearchRepository(conn))
    return conn, profile_service, glossary_service, template_service, search_service


def create_web_window(bridge):
    from cyberglossary.config.resources import web_dir
    from cyberglossary.ui.web.web_main_window import WebMainWindow

    return WebMainWindow(bridge, web_dir())


def create_tray(profile_service, initial_paused: bool = False):
    from cyberglossary.windows.tray import TrayController

    return TrayController(profile_service, initial_paused=initial_paused)


def run(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except Exception:
        import tempfile
        import traceback
        from datetime import UTC, datetime
        from pathlib import Path

        crash_log = Path(tempfile.gettempdir()) / "adudu_crash.log"
        try:
            with open(crash_log, "a", encoding="utf-8") as handle:
                handle.write(f"\n{datetime.now(UTC).isoformat(timespec='seconds')} CRASH\n")
                traceback.print_exc(file=handle)
        except OSError:
            traceback.print_exc()
        raise


def _run(argv: list[str] | None = None) -> int:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

    from cyberglossary.config import settings as settings_mod
    from cyberglossary.config.resources import resource_path, web_dir
    from cyberglossary.import_export.json_export import export_profile_json
    from cyberglossary.import_export.json_import import (
        ImportValidationError,
        import_profile,
        parse_json,
    )
    from cyberglossary.import_export.markdown_export import export_profile_markdown
    from cyberglossary.services.backup_service import BackupError, BackupService
    from cyberglossary.services.lookup_service import LookupResult, LookupService
    from cyberglossary.ui.hotkey_dialog import HotkeyCaptureDialog
    from cyberglossary.ui.web.bridge import Bridge
    from cyberglossary.ui.web.create_term_window import CreateTermWindow
    from cyberglossary.ui.web.launcher_window import LauncherWindow
    from cyberglossary.ui.web.lookup_popup import LookupPopupWindow
    from cyberglossary.ui.web.web_main_window import WebMainWindow
    from cyberglossary.windows.clipboard import WindowsClipboard
    from cyberglossary.windows.hotkey import Hotkey, HotkeyService, format_hotkey
    from cyberglossary.windows.text_capture import TextCapture

    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Single instance: if adudu is already running, ask it to come to the foreground
    # and exit this (redundant) launch instead of opening a second window.
    window = None
    popup = None
    launcher = None
    create_term_win = None
    from cyberglossary.windows.single_instance import (
        SingleInstanceServer,
        notify_running_instance,
        server_name,
    )

    if notify_running_instance(server_name()):
        return 0

    _pending_activate = False

    def _activate_window() -> None:
        nonlocal _pending_activate
        if window is None:
            _pending_activate = True
            return
        if popup is not None:
            popup.close_popup()
        window.show_window()

    # Keep the server alive for the whole session by parenting it to the app.
    SingleInstanceServer(server_name(), _activate_window, parent=app)

    icon_path = resource_path("resources/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    app_settings = settings_mod.load()

    conn, profile_service, glossary_service, template_service, search_service = build_services()
    tray = create_tray(profile_service, initial_paused=app_settings.lookup_paused)

    hotkey = Hotkey(app_settings.hotkey_modifiers, app_settings.hotkey_key)

    lookup = LookupService(
        TextCapture(WindowsClipboard()).capture,
        profile_service,
        glossary_service,
        search_service,
    )
    backup_service = BackupService(conn, paths.database_path())

    # References assigned after the window exists; used by the bridge callbacks below.
    hotkey_service: HotkeyService | None = None
    launcher_hotkey_service: HotkeyService | None = None

    def _active_profile_id() -> int | None:
        return profile_service.get_active_profile_id()

    def _notify(message: str) -> None:
        if window is not None:
            window.notify(message)

    # --- theme -----------------------------------------------------------

    def _set_theme(dark: bool) -> None:
        app_settings.theme = "dark" if dark else "light"
        settings_mod.save(app_settings)

    # --- hotkey / capture ------------------------------------------------

    def _apply_hotkey(new_hotkey: Hotkey) -> bool:
        ok = hotkey_service.change(new_hotkey)
        if ok:
            app_settings.hotkey_modifiers = new_hotkey.modifiers
            app_settings.hotkey_key = new_hotkey.key
            settings_mod.save(app_settings)
        return ok

    def _change_hotkey() -> None:
        capture = HotkeyCaptureDialog(hotkey_service.current_hotkey(), window)
        if capture.exec() == QDialog.DialogCode.Accepted:
            new_hotkey = capture.captured_hotkey()
            if new_hotkey is not None:
                _apply_hotkey(new_hotkey)

    # --- launcher (global search) ----------------------------------------

    def _copy_text(text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _on_launcher_recent(term_id: int) -> None:
        recents = app_settings.launcher_recent
        if term_id in recents:
            recents.remove(term_id)
        recents.insert(0, term_id)
        del recents[12:]
        settings_mod.save(app_settings)

    def _on_launcher_pin(term_id: int) -> None:
        pins = app_settings.launcher_pinned
        if term_id in pins:
            pins.remove(term_id)
        else:
            pins.insert(0, term_id)
        settings_mod.save(app_settings)

    def _ensure_launcher():
        nonlocal launcher
        if launcher is None:
            launcher = LauncherWindow(bridge, web_dir())
        return launcher

    def _on_launcher_hotkey() -> None:
        _ensure_launcher().show_launcher()

    def _close_launcher() -> None:
        nonlocal launcher
        if launcher is not None:
            launcher.close_launcher()
            launcher.deleteLater()
            launcher = None

    def _apply_launcher_hotkey(new_hotkey: Hotkey) -> bool:
        if launcher_hotkey_service is None:
            return False
        ok = launcher_hotkey_service.change(new_hotkey)
        if ok:
            app_settings.launcher_hotkey_modifiers = new_hotkey.modifiers
            app_settings.launcher_hotkey_key = new_hotkey.key
            settings_mod.save(app_settings)
        return ok

    def _change_launcher_hotkey() -> None:
        if launcher_hotkey_service is None:
            return
        capture = HotkeyCaptureDialog(launcher_hotkey_service.current_hotkey(), window)
        if capture.exec() == QDialog.DialogCode.Accepted:
            new_hotkey = capture.captured_hotkey()
            if new_hotkey is not None:
                _apply_launcher_hotkey(new_hotkey)

    def _set_capture(on: bool) -> None:
        paused = not on
        app_settings.lookup_paused = paused
        settings_mod.save(app_settings)
        if paused:
            hotkey_service.pause()
        elif not hotkey_service.resume():
            tray.notify("Hotkey", "Could not re-register the global hotkey.")

    def _on_pause(paused: bool) -> None:
        _set_capture(not paused)

    def _on_hotkey_pressed() -> None:
        # 1. Capture while the *other* app still has focus (Ctrl+C targets it).
        text = lookup.capture_and_normalize()
        if not text:
            result = LookupResult.not_found(None)
        else:
            # 2. Resolve through the existing LookupService.
            result = lookup.lookup(text)
        # 3. Show only the floating lookup popup (not the main window).
        if popup is not None:
            popup.show_result(_lookup_json(result))

    def _open_term_from_popup(term_id: int, edit_mode: bool) -> None:
        if popup is not None:
            popup.close_popup()
        if window is not None:
            window.show_window()
        bridge.openTermInWindow.emit(term_id, edit_mode)

    def _request_create_term(name: str) -> None:
        # Open only the standalone "New Term" window, not the whole application.
        nonlocal create_term_win
        if popup is not None:
            popup.close_popup()
        if create_term_win is None:
            create_term_win = CreateTermWindow(bridge, web_dir())
        bridge.setCreateTermName(name or "")
        create_term_win.show_create_term()

    def _close_create_term_window() -> None:
        nonlocal create_term_win
        if create_term_win is not None:
            create_term_win.close_create_term()
            create_term_win.deleteLater()
            create_term_win = None

    # --- file / data actions (native dialogs + existing handlers) --------

    def _file_action(key: str) -> None:
        actions = {
            "import-json": _import_json,
            "export-json": _export_json,
            "export-md": _export_markdown,
            "backup": _backup_database,
            "restore": _restore_database,
            "exit": _exit_application,
        }
        handler = actions.get(key)
        if handler is not None:
            handler()

    def _export_json() -> None:
        profile_id = _active_profile_id()
        if profile_id is None:
            _notify("No active profile selected.")
            return
        path, _ = QFileDialog.getSaveFileName(
            window, "Export Profile (JSON)", "cyberglossary-profile.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            text = export_profile_json(profile_id, profile_service, glossary_service, template_service)
            Path(path).write_text(text, encoding="utf-8")
            _notify("Profile exported successfully.")
        except Exception as exc:  # noqa: BLE001
            _notify(f"Export failed: {exc}")

    def _export_markdown() -> None:
        profile_id = _active_profile_id()
        if profile_id is None:
            _notify("No active profile selected.")
            return
        directory = QFileDialog.getExistingDirectory(window, "Export Profile (Markdown)")
        if not directory:
            return
        try:
            files = export_profile_markdown(
                profile_id, profile_service, glossary_service, template_service
            )
            for filename, content in files:
                Path(directory, filename).write_text(content, encoding="utf-8")
            _notify(f"Exported {len(files)} Markdown file(s).")
        except Exception as exc:  # noqa: BLE001
            _notify(f"Export failed: {exc}")

    def _import_json() -> None:
        path, _ = QFileDialog.getOpenFileName(window, "Import Profile (JSON)", "", "JSON (*.json)")
        if not path:
            return
        try:
            data = parse_json(Path(path).read_text(encoding="utf-8"))
        except ImportValidationError as exc:
            _notify(f"Invalid file: {exc}")
            return
        except OSError as exc:
            _notify(f"Could not read file: {exc}")
            return

        mode = _confirm_import()
        if mode is None:
            return
        try:
            result = import_profile(conn, data, mode)
        except ImportValidationError as exc:
            _notify(f"Import failed: {exc}")
            return
        profile_service.set_active_profile(result.profile_id)
        _reload()
        skipped = f"\nSkipped existing terms: {', '.join(result.terms_skipped)}" if result.terms_skipped else ""
        _notify(f"Imported profile '{result.profile_name}' ({result.terms_imported} terms).{skipped}")

    def _confirm_import() -> str | None:
        try:
            from PySide6.QtWidgets import QMessageBox

            box = QMessageBox(window)
            box.setWindowTitle("Import")
            box.setText("Import this profile into adudu?")
            merge_btn = box.addButton("Merge", QMessageBox.ButtonRole.AcceptRole)
            replace_btn = box.addButton("Replace", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() == merge_btn:
                return "merge"
            if box.clickedButton() == replace_btn:
                return "replace"
            return None
        except Exception:  # noqa: BLE001
            return None

    def _backup_database() -> None:
        directory = QFileDialog.getExistingDirectory(window, "Backup Database")
        if not directory:
            return
        try:
            path = backup_service.create_backup(directory)
            _notify(f"Backup created: {path}")
        except BackupError as exc:
            _notify(f"Backup failed: {exc}")

    def _restore_database() -> None:
        path, _ = QFileDialog.getOpenFileName(window, "Restore Database", "", "SQLite (*.db)")
        if not path:
            return
        box = QMessageBox(window)
        box.setWindowTitle("Restore Database")
        box.setText(
            "This will replace the current database.\n"
            "A safety backup of the current database will be created first."
        )
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        restore_btn = box.addButton("Restore", QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        if box.clickedButton() != restore_btn:
            return
        try:
            new_conn = backup_service.restore(path)
        except BackupError as exc:
            _notify(f"Restore failed: {exc}")
            return
        _rebuild(new_conn)

    def _exit_application() -> None:
        if hotkey_service is not None:
            hotkey_service.shutdown()
        if launcher_hotkey_service is not None:
            launcher_hotkey_service.shutdown()
        if launcher is not None:
            launcher.deleteLater()
        if create_term_win is not None:
            create_term_win.deleteLater()
        if window is not None:
            window.exit_application()
        app.quit()

    # --- bridge -----------------------------------------------------------

    def _get_hotkey_text() -> str:
        if hotkey_service is not None:
            return format_hotkey(hotkey_service.current_hotkey())
        return format_hotkey(hotkey)

    def _get_launcher_hotkey_text() -> str:
        if launcher_hotkey_service is not None:
            return format_hotkey(launcher_hotkey_service.current_hotkey())
        return format_hotkey(Hotkey(app_settings.launcher_hotkey_modifiers, app_settings.launcher_hotkey_key))

    def _get_third_party_notices() -> str:
        from cyberglossary.config.resources import resource_path

        path = resource_path("THIRD-PARTY-NOTICES")
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return "Third-party notices file could not be read."

    def _make_bridge() -> Bridge:
        return Bridge(
            profile_service,
            glossary_service,
            search_service,
            lookup,
            backup_service,
            app_settings,
            on_theme=_set_theme,
            on_file_action=_file_action,
            on_change_hotkey=_change_hotkey,
            on_capture_changed=_set_capture,
            on_exit=_exit_application,
            get_hotkey_text=_get_hotkey_text,
            on_ready=lambda: popup.on_bridge_ready() if popup is not None else None,
            on_close_popup=lambda: popup.close_popup() if popup is not None else None,
            on_open_term=_open_term_from_popup,
            on_start_move=lambda: popup.start_move() if popup is not None else None,
            on_start_resize=lambda edge: popup.start_resize(edge) if popup is not None else None,
            on_request_create_term=_request_create_term,
            on_copy_text=_copy_text,
            on_launcher_move=lambda: launcher.start_move() if launcher is not None else None,
            on_launcher_resize=lambda edge: launcher.start_resize(edge) if launcher is not None else None,
            on_launcher_minimize=lambda: launcher.minimize() if launcher is not None else None,
            on_launcher_restore=lambda: launcher.restore() if launcher is not None else None,
            on_launcher_close=_close_launcher,
            on_launcher_recent=_on_launcher_recent,
            on_launcher_pin=_on_launcher_pin,
            on_change_launcher_hotkey=_change_launcher_hotkey,
            get_launcher_hotkey_text=_get_launcher_hotkey_text,
            get_third_party_notices=_get_third_party_notices,
            on_create_term_move=lambda: create_term_win.start_move() if create_term_win is not None else None,
            on_create_term_resize=lambda edge: create_term_win.start_resize(edge) if create_term_win is not None else None,
            on_create_term_close=_close_create_term_window,
        )

    bridge = _make_bridge()
    window = WebMainWindow(bridge, web_dir())
    popup = LookupPopupWindow(bridge, web_dir())
    window.show()

    if _pending_activate:
        _pending_activate = False
        window.show_window()

    hotkey_service = HotkeyService(int(window.winId()), hotkey)
    hotkey_service.install_filter(app)

    launcher_hotkey = Hotkey(app_settings.launcher_hotkey_modifiers, app_settings.launcher_hotkey_key)
    launcher_hotkey_service = HotkeyService(int(window.winId()), launcher_hotkey, hotkey_id=2)
    launcher_hotkey_service.install_filter(app)
    launcher_hotkey_service.hotkey_pressed.connect(_on_launcher_hotkey)
    launcher_hotkey_service.register()

    def _reload() -> None:
        if window is not None:
            window.bridge.dataChanged.emit()

    def _rebuild(new_conn) -> None:
        nonlocal conn, profile_service, glossary_service, template_service
        nonlocal search_service, lookup, backup_service, hotkey_service, tray, window, bridge, popup
        nonlocal launcher, launcher_hotkey_service, create_term_win

        was_paused = hotkey_service.is_paused()
        hotkey_service.shutdown()
        if launcher_hotkey_service is not None:
            launcher_hotkey_service.shutdown()

        old_window = window
        old_tray = tray
        old_popup = popup
        old_window.close()
        old_tray.hide()
        old_popup.close_popup()
        old_window.deleteLater()
        old_tray.deleteLater()
        old_popup.deleteLater()
        if launcher is not None:
            launcher.close_launcher()
            launcher.deleteLater()
            launcher = None
        if create_term_win is not None:
            create_term_win.close_create_term()
            create_term_win.deleteLater()
            create_term_win = None

        conn, profile_service, glossary_service, template_service, search_service = (
            _build_services_from_conn(new_conn)
        )
        tray = create_tray(profile_service, initial_paused=app_settings.lookup_paused)
        lookup = LookupService(
            TextCapture(WindowsClipboard()).capture,
            profile_service,
            glossary_service,
            search_service,
        )
        backup_service = BackupService(conn, paths.database_path())

        # Rebuild the bridge + web shell + lookup popup against the restored database.
        bridge = _make_bridge()
        window = WebMainWindow(bridge, web_dir())
        popup = LookupPopupWindow(bridge, web_dir())
        window.show()

        hotkey_service = HotkeyService(
            int(window.winId()), Hotkey(app_settings.hotkey_modifiers, app_settings.hotkey_key)
        )
        hotkey_service.install_filter(app)

        launcher_hotkey_service = HotkeyService(
            int(window.winId()),
            Hotkey(app_settings.launcher_hotkey_modifiers, app_settings.launcher_hotkey_key),
            hotkey_id=2,
        )
        launcher_hotkey_service.install_filter(app)
        launcher_hotkey_service.hotkey_pressed.connect(_on_launcher_hotkey)
        launcher_hotkey_service.register()

        _wire_tray()

        if was_paused:
            hotkey_service.pause()
        elif not hotkey_service.register():
            tray.notify("Hotkey", "Could not re-register the global hotkey.")

        window.show()
        tray.show()

    def _wire_tray() -> None:
        tray.open_requested.connect(window.show_window)
        tray.settings_requested.connect(lambda: bridge.openSettings.emit())
        tray.exit_requested.connect(_exit_application)
        tray.profile_selected.connect(
            lambda pid: (profile_service.set_active_profile(pid), _reload())
        )
        tray.pause_toggled.connect(_on_pause)
        hotkey_service.hotkey_pressed.connect(_on_hotkey_pressed)

    _wire_tray()

    # Startup registration.
    if app_settings.lookup_paused:
        hotkey_service.pause()
    elif not hotkey_service.register():
        tray.notify(
            "Hotkey",
            f"Could not register {format_hotkey(hotkey)}. Change it under Settings.",
        )

    tray.show()
    return app.exec()


def _lookup_json(result) -> str:
    from cyberglossary.ui.web.bridge import _lookup_dict

    return json.dumps(_lookup_dict(result))


def _persist_paused(app_settings, paused: bool) -> None:
    from cyberglossary.config import settings as settings_mod

    app_settings.lookup_paused = paused
    settings_mod.save(app_settings)
