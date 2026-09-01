"""Tests for dialog centering geometry."""

from __future__ import annotations

from cyberglossary.ui.dialog_utils import centered_position


def test_centered_on_parent():
    # dialog 400x300, parent (100,100,800,600), screen (0,0,1920,1080)
    x, y = centered_position(400, 300, (100, 100, 800, 600), (0, 0, 1920, 1080))
    assert (x, y) == (300, 250)


def test_centered_on_screen_when_no_parent():
    x, y = centered_position(400, 300, None, (0, 0, 1920, 1080))
    assert (x, y) == (760, 390)


def test_clamped_to_screen():
    # parent near the right edge would push the dialog off-screen.
    x, y = centered_position(400, 300, (1700, 100, 800, 600), (0, 0, 1920, 1080))
    assert x == 1520
    assert y == 250


def test_multi_monitor_centering():
    # monitor 2 begins at x=1920; parent lives there.
    x, y = centered_position(400, 300, (2000, 100, 800, 600), (1920, 0, 1920, 1080))
    assert (x, y) == (2200, 250)
