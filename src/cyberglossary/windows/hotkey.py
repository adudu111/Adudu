"""Global hotkey: structured representation, Win32 ``RegisterHotKey`` integration, and a
clean ``HotkeyService`` abstraction.

The only Win32 calls are in ``_register_native``/``_unregister_native`` (ctypes), so the
state machine is fully unit-testable with those methods mocked. The UI never calls
``RegisterHotKey`` directly.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, Signal

# Win32 modifier flags for RegisterHotKey.
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

WM_HOTKEY = 0x0312

# Non-modifier virtual-key codes (Win32).
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_HOME = 0x24
VK_END = 0x23
VK_PRIOR = 0x21  # Page Up
VK_NEXT = 0x22   # Page Down
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_MBUTTON = 0x04
VK_XBUTTON1 = 0x05  # Mouse MB4
VK_XBUTTON2 = 0x06  # Mouse MB5
VK_OEM_1 = 0xBA   # ;:
VK_OEM_PLUS = 0xBB  # =+
VK_OEM_COMMA = 0xBC  # ,<
VK_OEM_MINUS = 0xBD  # -_
VK_OEM_PERIOD = 0xBE  # .>
VK_OEM_2 = 0xBF  # /?
VK_OEM_3 = 0xC0  # `~
VK_OEM_4 = 0xDB  # [{
VK_OEM_5 = 0xDC  # \|
VK_OEM_6 = 0xDD  # ]}
VK_OEM_7 = 0xDE  # '"


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


@dataclass(frozen=True)
class Hotkey:
    """A structured global hotkey: modifier bitmask + non-modifier virtual-key code."""

    modifiers: int
    key: int

    def is_valid(self) -> bool:
        """A valid hotkey requires at least one non-modifier key."""
        return self.key != 0


DEFAULT_HOTKEY = Hotkey(MOD_CONTROL | MOD_SHIFT, 0x44)  # Ctrl+Shift+D


# --- parse / format -------------------------------------------------------


def key_to_name(vk: int) -> str:
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x70 + 1}"
    names = {
        VK_BACK: "Backspace",
        VK_TAB: "Tab",
        VK_RETURN: "Enter",
        VK_ESCAPE: "Esc",
        VK_SPACE: "Space",
        VK_INSERT: "Insert",
        VK_DELETE: "Delete",
        VK_HOME: "Home",
        VK_END: "End",
        VK_PRIOR: "Page Up",
        VK_NEXT: "Page Down",
        VK_LEFT: "Left",
        VK_UP: "Up",
        VK_RIGHT: "Right",
        VK_DOWN: "Down",
        VK_MBUTTON: "Middle Click",
        VK_XBUTTON1: "Mouse MB4",
        VK_XBUTTON2: "Mouse MB5",
        VK_OEM_1: ";",
        VK_OEM_PLUS: "=",
        VK_OEM_COMMA: ",",
        VK_OEM_MINUS: "-",
        VK_OEM_PERIOD: ".",
        VK_OEM_2: "/",
        VK_OEM_3: "`",
        VK_OEM_4: "[",
        VK_OEM_5: "\\",
        VK_OEM_6: "]",
        VK_OEM_7: "'",
    }
    return names.get(vk, f"VK{vk}")


def name_to_key(name: str) -> int:
    name = name.strip()
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    upper = name.upper()
    if upper.startswith("F") and upper[1:].isdigit():
        number = int(upper[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1
    reverse = {
        "BACKSPACE": VK_BACK,
        "TAB": VK_TAB,
        "ENTER": VK_RETURN,
        "ESC": VK_ESCAPE,
        "SPACE": VK_SPACE,
        "INSERT": VK_INSERT,
        "DELETE": VK_DELETE,
        "HOME": VK_HOME,
        "END": VK_END,
        "PAGEUP": VK_PRIOR,
        "PAGEDOWN": VK_NEXT,
        "LEFT": VK_LEFT,
        "UP": VK_UP,
        "RIGHT": VK_RIGHT,
        "DOWN": VK_DOWN,
        "MIDDLE CLICK": VK_MBUTTON,
        "MOUSE MB4": VK_XBUTTON1,
        "MOUSE MB5": VK_XBUTTON2,
    }
    return reverse.get(upper, 0)


def format_hotkey(hotkey: Hotkey) -> str:
    parts: list[str] = []
    if hotkey.modifiers & MOD_CONTROL:
        parts.append("Ctrl")
    if hotkey.modifiers & MOD_ALT:
        parts.append("Alt")
    if hotkey.modifiers & MOD_SHIFT:
        parts.append("Shift")
    if hotkey.modifiers & MOD_WIN:
        parts.append("Win")
    parts.append(key_to_name(hotkey.key))
    return " + ".join(parts)


def parse_hotkey(text: str) -> Hotkey:
    modifiers = 0
    key = 0
    for part in text.split("+"):
        token = part.strip().lower()
        if token in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif token == "shift":
            modifiers |= MOD_SHIFT
        elif token == "alt":
            modifiers |= MOD_ALT
        elif token in ("win", "meta", "windows"):
            modifiers |= MOD_WIN
        else:
            key = name_to_key(part)
    return Hotkey(modifiers, key)


# --- Qt key mapping -------------------------------------------------------


def qt_key_to_vk(key: int) -> int | None:
    """Map a ``Qt.Key`` value to a Win32 virtual-key code, or None if unsupported."""
    k = int(key)
    a = int(Qt.Key.Key_A)
    z = int(Qt.Key.Key_Z)
    if a <= k <= z:
        return 0x41 + (k - a)
    d0 = int(Qt.Key.Key_0)
    d9 = int(Qt.Key.Key_9)
    if d0 <= k <= d9:
        return 0x30 + (k - d0)
    f1 = int(Qt.Key.Key_F1)
    f24 = int(Qt.Key.Key_F24)
    if f1 <= k <= f24:
        return 0x70 + (k - f1)
    table = {
        Qt.Key.Key_Backspace: VK_BACK,
        Qt.Key.Key_Tab: VK_TAB,
        Qt.Key.Key_Return: VK_RETURN,
        Qt.Key.Key_Enter: VK_RETURN,
        Qt.Key.Key_Escape: VK_ESCAPE,
        Qt.Key.Key_Space: VK_SPACE,
        Qt.Key.Key_Insert: VK_INSERT,
        Qt.Key.Key_Delete: VK_DELETE,
        Qt.Key.Key_Home: VK_HOME,
        Qt.Key.Key_End: VK_END,
        Qt.Key.Key_PageUp: VK_PRIOR,
        Qt.Key.Key_PageDown: VK_NEXT,
        Qt.Key.Key_Left: VK_LEFT,
        Qt.Key.Key_Up: VK_UP,
        Qt.Key.Key_Right: VK_RIGHT,
        Qt.Key.Key_Down: VK_DOWN,
        Qt.Key.Key_Semicolon: VK_OEM_1,
        Qt.Key.Key_Equal: VK_OEM_PLUS,
        Qt.Key.Key_Comma: VK_OEM_COMMA,
        Qt.Key.Key_Minus: VK_OEM_MINUS,
        Qt.Key.Key_Period: VK_OEM_PERIOD,
        Qt.Key.Key_Slash: VK_OEM_2,
        Qt.Key.Key_QuoteLeft: VK_OEM_3,
        Qt.Key.Key_BracketLeft: VK_OEM_4,
        Qt.Key.Key_Backslash: VK_OEM_5,
        Qt.Key.Key_BracketRight: VK_OEM_6,
        Qt.Key.Key_Apostrophe: VK_OEM_7,
    }
    return table.get(k)


def _mods_from_qt(modifiers: Qt.KeyboardModifier) -> int:
    mods = 0
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        mods |= MOD_CONTROL
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        mods |= MOD_SHIFT
    if modifiers & Qt.KeyboardModifier.AltModifier:
        mods |= MOD_ALT
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        mods |= MOD_WIN
    return mods


def hotkey_from_qt_event(key: int, modifiers: Qt.KeyboardModifier) -> Hotkey | None:
    """Build a ``Hotkey`` from a Qt key event. Accepts any single key (with or without a
    modifier), including function, navigation, and punctuation keys. Modifier-only
    combinations are rejected."""
    vk = qt_key_to_vk(key)
    if vk is None:
        return None
    return Hotkey(_mods_from_qt(modifiers), vk)


def hotkey_from_qt_mouse(button: Qt.MouseButton, modifiers: Qt.KeyboardModifier) -> Hotkey | None:
    """Build a ``Hotkey`` from a Qt mouse button (middle / back / forward)."""
    vk = None
    if button == Qt.MouseButton.MiddleButton:
        vk = VK_MBUTTON
    elif button == Qt.MouseButton.BackButton:
        vk = VK_XBUTTON1  # Mouse MB4
    elif button == Qt.MouseButton.ForwardButton:
        vk = VK_XBUTTON2  # Mouse MB5
    if vk is None:
        return None
    return Hotkey(_mods_from_qt(modifiers), vk)


# --- native event filter --------------------------------------------------


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, callback) -> None:
        super().__init__()
        self._id = hotkey_id
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = _MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                self._callback()
                return True, 0
        return False, 0


# --- service --------------------------------------------------------------


class HotkeyService(QObject):
    hotkey_pressed = Signal()

    def __init__(
        self,
        hwnd: int = 0,
        hotkey: Hotkey = DEFAULT_HOTKEY,
        parent: QObject | None = None,
        hotkey_id: int = 1,
    ):
        super().__init__(parent)
        self._hwnd = hwnd
        self._hotkey = hotkey
        self._id = hotkey_id
        self._registered = False
        self._paused = False
        self._filter: _HotkeyEventFilter | None = None

    # --- native integration (mock these in tests) -------------------------

    def _register_native(self, hotkey: Hotkey) -> bool:
        return bool(
            ctypes.windll.user32.RegisterHotKey(
                self._hwnd, self._id, hotkey.modifiers, hotkey.key
            )
        )

    def _unregister_native(self) -> bool:
        return bool(ctypes.windll.user32.UnregisterHotKey(self._hwnd, self._id))

    def install_filter(self, app) -> None:
        if self._filter is None:
            self._filter = _HotkeyEventFilter(self._id, self.hotkey_pressed.emit)
            app.installNativeEventFilter(self._filter)

    # --- state machine ----------------------------------------------------

    def register(self) -> bool:
        if self._paused or self._registered:
            return self._registered
        self._registered = self._register_native(self._hotkey)
        return self._registered

    def unregister(self) -> None:
        if self._registered:
            self._unregister_native()
        self._registered = False

    def change(self, new_hotkey: Hotkey) -> bool:
        """Validate + swap the hotkey atomically (never leaves no working hotkey)."""
        if not new_hotkey.is_valid():
            return False
        was_registered = self._registered
        if was_registered:
            self.unregister()

        if self._paused:
            # Paused: update configuration only; do not register until resume.
            self._hotkey = new_hotkey
            return True

        if self._register_native(new_hotkey):
            self._hotkey = new_hotkey
            self._registered = True
            return True

        if was_registered:
            # Roll back to the old, working hotkey.
            self._registered = self._register_native(self._hotkey)
        return False

    def pause(self) -> None:
        self._paused = True
        self.unregister()

    def resume(self) -> bool:
        self._paused = False
        return self.register()

    def shutdown(self) -> None:
        self.unregister()

    # --- accessors --------------------------------------------------------

    def is_registered(self) -> bool:
        return self._registered

    def is_paused(self) -> bool:
        return self._paused

    def current_hotkey(self) -> Hotkey:
        return self._hotkey
