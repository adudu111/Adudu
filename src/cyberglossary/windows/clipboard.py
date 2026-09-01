"""Clipboard abstraction for selected-text capture.

``ClipboardProvider`` defines the interface the capture pipeline needs. The Windows
implementation uses pywin32 lazily (imported inside each method) so unit tests never
require a real clipboard. No clipboard contents are ever logged.
"""

from __future__ import annotations


class ClipboardProvider:
    def get_sequence_number(self) -> int:
        raise NotImplementedError

    def read_text(self) -> str | None:
        raise NotImplementedError

    def write_text(self, text: str) -> None:
        raise NotImplementedError

    def send_copy(self) -> None:
        raise NotImplementedError


class WindowsClipboard(ClipboardProvider):
    def get_sequence_number(self) -> int:
        import win32clipboard

        return win32clipboard.GetClipboardSequenceNumber()

    def read_text(self) -> str | None:
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:  # noqa: BLE001 - clipboard may be locked; fail gracefully
            return None
        return None

    def write_text(self, text: str) -> None:
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:  # noqa: BLE001, S110 - clipboard may be locked; fail gracefully
            pass

    def send_copy(self) -> None:
        import win32api
        import win32con

        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord("C"), 0, 0, 0)
        win32api.keybd_event(ord("C"), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
