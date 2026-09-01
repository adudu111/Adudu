"""Selected-text capture (clipboard-first strategy).

Snapshot the clipboard, send Ctrl+C, poll for a sequence-number change, read the text,
then restore the previous text *only* when safe. Never monitors the clipboard, never
logs or persists captured text.
"""

from __future__ import annotations

import time

from cyberglossary.windows.clipboard import ClipboardProvider


class TextCapture:
    def __init__(
        self,
        clipboard: ClipboardProvider,
        poll_timeout: float = 0.5,
        poll_interval: float = 0.03,
        pre_copy_delay: float = 0.15,
    ) -> None:
        self._clipboard = clipboard
        self._timeout = poll_timeout
        self._interval = poll_interval
        self._pre_copy_delay = pre_copy_delay

    def capture(self) -> str | None:
        """Return the currently selected text, or ``None`` if capture failed."""
        seq_before = self._clipboard.get_sequence_number()
        saved_text = self._clipboard.read_text()

        # The global hotkey fires on key-down, so the user's modifier keys may still be
        # held when we synthesize Ctrl+C. A brief delay lets them be released, so the
        # copy is a clean Ctrl+C rather than e.g. Ctrl+Shift+C (which Chrome routes to
        # DevTools instead of copy).
        if self._pre_copy_delay:
            time.sleep(self._pre_copy_delay)

        self._clipboard.send_copy()

        text: str | None = None
        seq_after = seq_before
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            current = self._clipboard.get_sequence_number()
            if current != seq_before:
                text = self._clipboard.read_text()
                seq_after = current
                break
            time.sleep(self._interval)

        self._restore(saved_text, text, seq_after)
        return text

    def _restore(self, saved_text: str | None, captured_text: str | None, seq_after: int) -> None:
        # Only restore text we previously had, and only if the clipboard hasn't changed
        # again since we read it (avoid clobbering another app's newer write).
        if saved_text is None or captured_text is None:
            return
        if self._clipboard.get_sequence_number() != seq_after:
            return
        try:
            self._clipboard.write_text(saved_text)
        except Exception:  # noqa: BLE001, S110 - best-effort restore, never crash
            pass
