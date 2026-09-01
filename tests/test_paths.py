"""Tests for application path resolution."""

from __future__ import annotations

from cyberglossary.config import paths


def test_app_data_dir_uses_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.DATA_DIR_ENV_VAR, str(tmp_path / "custom"))
    assert paths.app_data_dir() == tmp_path / "custom"


def test_app_data_dir_uses_userprofile(tmp_path, monkeypatch):
    """Resolved from USERPROFILE so Store-Python virtualization can't redirect it."""
    monkeypatch.delenv(paths.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "ignored"))
    assert paths.app_data_dir() == tmp_path / "AppData" / "Roaming" / paths.APP_DIR_NAME


def test_database_and_settings_paths_live_under_app_data(data_dir):
    root = paths.app_data_dir()
    assert paths.database_path().parent == root
    assert paths.settings_path().parent == root
    assert paths.backups_dir() == root / paths.BACKUPS_DIR_NAME


def test_ensure_dirs_creates_tree(data_dir):
    root = paths.ensure_dirs()
    assert root.is_dir()
    assert paths.backups_dir().is_dir()
