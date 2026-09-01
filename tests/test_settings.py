"""Tests for application settings (JSON-backed preferences)."""

from __future__ import annotations

import json

from cyberglossary.config import settings


def test_defaults():
    s = settings.AppSettings()
    assert s.theme == settings.THEME_DARK
    assert s.backup_dir is None
    assert s.lookup_paused is False
    assert s.validate() == []


def test_lookup_paused_roundtrip(tmp_path):
    target = tmp_path / "settings.json"
    original = settings.AppSettings(lookup_paused=True)
    settings.save(original, target)
    loaded = settings.load(target)
    assert loaded.lookup_paused is True


def test_save_load_roundtrip(tmp_path):
    target = tmp_path / "settings.json"
    original = settings.AppSettings(theme=settings.THEME_LIGHT, backup_dir=str(tmp_path / "bk"))
    settings.save(original, target)
    loaded = settings.load(target)
    assert loaded == original


def test_load_missing_returns_defaults(tmp_path):
    loaded = settings.load(tmp_path / "nope.json")
    assert loaded == settings.AppSettings()


def test_load_invalid_json_returns_defaults(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{ not valid json", encoding="utf-8")
    assert settings.load(target) == settings.AppSettings()


def test_load_ignores_unknown_keys(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"theme": "light", "surprise": 123}), encoding="utf-8")
    loaded = settings.load(target)
    assert loaded.theme == settings.THEME_LIGHT
    assert not hasattr(loaded, "surprise")


def test_validate_rejects_bad_theme():
    s = settings.AppSettings(theme="neon")
    assert s.validate()
