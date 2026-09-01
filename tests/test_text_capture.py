"""Tests for clipboard-first selected-text capture (using a fake clipboard)."""

from __future__ import annotations

from cyberglossary.windows.text_capture import TextCapture


class FakeClipboard:
    def __init__(self):
        self.seq = 1
        self.text = None
        self.write_calls = []

    def get_sequence_number(self):
        return self.seq

    def read_text(self):
        return self.text

    def write_text(self, text):
        self.text = text
        self.seq += 1
        self.write_calls.append(text)

    def send_copy(self):
        # Overridden per test to simulate the OS copying selected text.
        pass


def _capture(clipboard, **kwargs):
    return TextCapture(
        clipboard, poll_timeout=0.2, poll_interval=0.0, pre_copy_delay=0.0, **kwargs
    ).capture()


def test_successful_capture_restores_previous_text():
    clip = FakeClipboard()
    clip.text = "OLD"

    def send_copy():
        clip.seq += 1
        clip.text = "LDAP"

    clip.send_copy = send_copy

    assert _capture(clip) == "LDAP"
    assert clip.text == "OLD"  # restored
    assert clip.write_calls == ["OLD"]


def test_empty_clipboard_does_not_restore():
    clip = FakeClipboard()
    clip.text = None

    def send_copy():
        clip.seq += 1
        clip.text = "LDAP"

    clip.send_copy = send_copy

    assert _capture(clip) == "LDAP"
    assert clip.write_calls == []  # nothing to restore


def test_timeout_returns_none():
    clip = FakeClipboard()
    clip.text = "OLD"

    def send_copy():
        pass  # clipboard never changes

    clip.send_copy = send_copy

    assert _capture(clip) is None


def test_capture_with_no_text_after_copy_returns_none():
    clip = FakeClipboard()
    clip.text = None

    def send_copy():
        clip.seq += 1  # changed, but still no text (e.g. locked)

    clip.send_copy = send_copy

    assert _capture(clip) is None


def test_restore_failure_does_not_crash():
    clip = FakeClipboard()
    clip.text = "OLD"

    def send_copy():
        clip.seq += 1
        clip.text = "LDAP"

    def write_text(_text):
        raise RuntimeError("clipboard locked")

    clip.send_copy = send_copy
    clip.write_text = write_text

    assert _capture(clip) == "LDAP"  # must not crash


def test_another_app_change_is_not_clobbered():
    clip = FakeClipboard()
    clip.text = "OLD"
    raced = False

    def send_copy():
        clip.seq += 1
        clip.text = "LDAP"

    def read_text():
        nonlocal raced
        text = clip.text
        if text == "LDAP" and not raced:
            raced = True
            # Simulate another app writing after we read the captured text.
            clip.text = "SOMEONE ELSE"
            clip.seq += 1
        return text

    clip.send_copy = send_copy
    clip.read_text = read_text

    assert _capture(clip) == "LDAP"
    assert clip.text == "SOMEONE ELSE"  # not clobbered
    assert clip.write_calls == []


def test_pre_copy_delay_allows_modifier_release(monkeypatch):
    import time as time_module

    clip = FakeClipboard()
    clip.text = "OLD"
    order = []
    sleeps = []

    def send_copy():
        order.append("copy")
        clip.seq += 1
        clip.text = "LDAP"

    clip.send_copy = send_copy

    def fake_sleep(seconds):
        sleeps.append(seconds)
        order.append("sleep")

    monkeypatch.setattr(time_module, "sleep", fake_sleep)

    capture = TextCapture(clip, poll_timeout=0.2, poll_interval=0.0, pre_copy_delay=0.15)
    result = capture.capture()

    assert result == "LDAP"
    assert 0.15 in sleeps
    assert order.index("sleep") < order.index("copy")
