"""Tests for the hotkey representation and HotkeyService state machine."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt

from cyberglossary.windows.hotkey import (
    DEFAULT_HOTKEY,
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    Hotkey,
    HotkeyService,
    format_hotkey,
    hotkey_from_qt_event,
    hotkey_from_qt_mouse,
    name_to_key,
    parse_hotkey,
    qt_key_to_vk,
)


class FakeBackend:
    """Records register/unregister calls and returns queued results."""

    def __init__(self):
        self.results: list[bool] = []
        self.register_calls: list[Hotkey] = []
        self.unregister_calls: list[bool] = []
        self.registered = False

    def register(self, hotkey: Hotkey) -> bool:
        self.register_calls.append(hotkey)
        result = self.results.pop(0) if self.results else True
        if result:
            self.registered = True
        return result

    def unregister(self) -> bool:
        self.unregister_calls.append(True)
        self.registered = False
        return True


def make_service(monkeypatch, backend, hotkey=DEFAULT_HOTKEY):
    service = HotkeyService(0, hotkey)
    monkeypatch.setattr(service, "_register_native", backend.register)
    monkeypatch.setattr(service, "_unregister_native", backend.unregister)
    return service


# --- representation --------------------------------------------------------


def test_default_hotkey():
    assert DEFAULT_HOTKEY == Hotkey(MOD_CONTROL | MOD_SHIFT, 0x44)
    assert format_hotkey(DEFAULT_HOTKEY) == "Ctrl + Shift + D"


def test_format_various():
    assert format_hotkey(Hotkey(MOD_CONTROL | MOD_ALT, 0x4C)) == "Ctrl + Alt + L"
    assert format_hotkey(Hotkey(MOD_ALT | MOD_SHIFT, 0x47)) == "Alt + Shift + G"
    assert format_hotkey(Hotkey(MOD_CONTROL, 0x77)) == "Ctrl + F8"
    assert format_hotkey(Hotkey(0, 0x78)) == "F9"


def test_parse_hotkey():
    assert parse_hotkey("Ctrl+Shift+D") == DEFAULT_HOTKEY
    assert parse_hotkey("Ctrl+Alt+L") == Hotkey(MOD_CONTROL | MOD_ALT, 0x4C)
    assert parse_hotkey("Alt+Shift+G") == Hotkey(MOD_ALT | MOD_SHIFT, 0x47)
    assert parse_hotkey("Ctrl+F8") == Hotkey(MOD_CONTROL, 0x77)
    assert parse_hotkey("F9") == Hotkey(0, 0x78)


def test_parse_format_roundtrip():
    for text in ("Ctrl+Shift+D", "Ctrl+Alt+L", "Alt+Shift+G", "Ctrl+F8", "F9"):
        assert parse_hotkey(format_hotkey(parse_hotkey(text))) == parse_hotkey(text)


def test_modifier_only_is_invalid():
    assert Hotkey(MOD_CONTROL | MOD_SHIFT, 0).is_valid() is False
    assert Hotkey(MOD_CONTROL, 0).is_valid() is False
    assert parse_hotkey("Ctrl+Shift").is_valid() is False


def test_hotkey_is_valid():
    assert Hotkey(0, 0x78).is_valid() is True  # F9 alone
    assert Hotkey(MOD_CONTROL | MOD_SHIFT, 0x44).is_valid() is True


def test_name_to_key():
    assert name_to_key("D") == 0x44
    assert name_to_key("F8") == 0x77
    assert name_to_key("0") == 0x30
    assert name_to_key("Bogus") == 0


def test_qt_key_to_vk():
    assert qt_key_to_vk(Qt.Key.Key_D) == 0x44
    assert qt_key_to_vk(Qt.Key.Key_F8) == 0x77
    assert qt_key_to_vk(Qt.Key.Key_0) == 0x30
    assert qt_key_to_vk(Qt.Key.Key_Control) is None


def test_hotkey_from_qt_event():
    mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    assert hotkey_from_qt_event(Qt.Key.Key_D, mods) == DEFAULT_HOTKEY
    assert hotkey_from_qt_event(Qt.Key.Key_F9, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x78)
    assert hotkey_from_qt_event(Qt.Key.Key_Control, mods) is None  # modifier-only


def test_hotkey_accepts_single_and_navigation_keys():
    # A single key with no modifier is a valid, capturable hotkey.
    assert hotkey_from_qt_event(Qt.Key.Key_F6, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x75)
    assert hotkey_from_qt_event(Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x26)
    assert hotkey_from_qt_event(Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x25)
    assert hotkey_from_qt_event(Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier) == Hotkey(MOD_CONTROL, 0x20)
    assert hotkey_from_qt_event(Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier) == Hotkey(MOD_ALT, 0x28)


def test_hotkey_from_mouse():
    assert hotkey_from_qt_mouse(Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x04)
    assert hotkey_from_qt_mouse(Qt.MouseButton.BackButton, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x05)
    assert hotkey_from_qt_mouse(Qt.MouseButton.ForwardButton, Qt.KeyboardModifier.NoModifier) == Hotkey(0, 0x06)
    assert hotkey_from_qt_mouse(Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier) is None
    assert format_hotkey(Hotkey(0, 0x04)) == "Middle Click"
    assert format_hotkey(Hotkey(MOD_CONTROL, 0x06)) == "Ctrl + Mouse MB5"


def test_qt_key_to_vk_navigation_and_punctuation():
    assert qt_key_to_vk(Qt.Key.Key_PageUp) == 0x21
    assert qt_key_to_vk(Qt.Key.Key_Delete) == 0x2E
    assert qt_key_to_vk(Qt.Key.Key_Semicolon) == 0xBA
    assert qt_key_to_vk(Qt.Key.Key_Slash) == 0xBF
    assert qt_key_to_vk(Qt.Key.Key_Tab) == 0x09


# --- service state machine -------------------------------------------------


def test_register_success(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    assert service.register() is True
    assert service.is_registered() is True


def test_register_failure(monkeypatch):
    backend = FakeBackend()
    backend.results = [False]
    service = make_service(monkeypatch, backend)
    assert service.register() is False
    assert service.is_registered() is False


def test_change_success(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    service.register()
    new = Hotkey(MOD_CONTROL | MOD_ALT, 0x4C)
    assert service.change(new) is True
    assert service.current_hotkey() == new
    assert service.is_registered() is True


def test_change_failure_keeps_old(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    service.register()
    old = service.current_hotkey()
    new = Hotkey(MOD_CONTROL | MOD_ALT, 0x4C)
    backend.results = [False, True]  # new fails, old re-registers
    assert service.change(new) is False
    assert service.current_hotkey() == old
    assert service.is_registered() is True
    assert backend.register_calls == [old, new, old]


def test_change_invalid_rejected(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    service.register()
    invalid = Hotkey(MOD_CONTROL | MOD_SHIFT, 0)  # modifier-only
    assert service.change(invalid) is False
    assert service.current_hotkey() == DEFAULT_HOTKEY


def test_pause_resume(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    service.register()
    service.pause()
    assert service.is_paused() is True
    assert service.is_registered() is False
    assert service.resume() is True
    assert service.is_paused() is False
    assert service.is_registered() is True


def test_change_while_paused(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    service.register()
    service.pause()
    new = Hotkey(MOD_ALT, 0x78)  # Alt+F9
    assert service.change(new) is True
    assert service.current_hotkey() == new
    assert service.is_registered() is False  # not registered while paused
    assert service.resume() is True
    assert service.is_registered() is True
    assert backend.register_calls[-1] == new  # last registration is the new hotkey


def test_shutdown_unregisters(monkeypatch):
    backend = FakeBackend()
    service = make_service(monkeypatch, backend)
    service.register()
    service.shutdown()
    assert service.is_registered() is False
    assert len(backend.unregister_calls) == 1


def test_startup_failure_does_not_crash(monkeypatch):
    backend = FakeBackend()
    backend.results = [False]
    service = make_service(monkeypatch, backend)
    assert service.register() is False


# --- capture dialog --------------------------------------------------------


def test_capture_dialog_detects_combination(qapp):
    from PySide6.QtGui import QKeyEvent

    from cyberglossary.ui.hotkey_dialog import HotkeyCaptureDialog

    dialog = HotkeyCaptureDialog(DEFAULT_HOTKEY)
    mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_D, mods)
    dialog.keyPressEvent(event)

    assert dialog.captured_hotkey() == DEFAULT_HOTKEY
    assert dialog.save_btn.isEnabled() is True


def test_capture_dialog_rejects_modifier_only(qapp):
    from PySide6.QtGui import QKeyEvent

    from cyberglossary.ui.hotkey_dialog import HotkeyCaptureDialog

    dialog = HotkeyCaptureDialog(DEFAULT_HOTKEY)
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
    dialog.keyPressEvent(event)

    assert dialog.captured_hotkey() is None
    assert dialog.save_btn.isEnabled() is False


def test_settings_dialog_apply(qapp):
    from cyberglossary.ui.hotkey_dialog import HotkeySettingsDialog

    results = []

    def on_apply(hotkey):
        results.append(hotkey)
        return True

    dialog = HotkeySettingsDialog(DEFAULT_HOTKEY, on_apply)
    new = Hotkey(MOD_CONTROL | MOD_ALT, 0x4C)
    dialog._apply(new)
    assert results == [new]
    assert "Ctrl + Alt + L" in dialog.current_label.text()
