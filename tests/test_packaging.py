"""Tests for packaging-related resources, version metadata, and path behavior."""

from __future__ import annotations

from pathlib import Path

import cyberglossary
from cyberglossary.config import paths
from cyberglossary.config.resources import resource_path
from cyberglossary.database import migrations

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_version_is_defined():
    assert isinstance(cyberglossary.__version__, str)
    parts = cyberglossary.__version__.split(".")
    assert len(parts) >= 2


def test_schema_sql_loads():
    assert "CREATE TABLE profiles" in migrations._SCHEMA_SQL
    assert "CREATE VIRTUAL TABLE terms_fts" in migrations._SCHEMA_SQL


def test_version_info_file_exists_and_matches():
    version_info = PROJECT_ROOT / "packaging" / "version_info.txt"
    text = version_info.read_text(encoding="utf-8")
    assert "ProductName" in text
    assert "CyberGlossary" in text
    assert "FileDescription" in text


def test_icon_resource_exists():
    assert (PROJECT_ROOT / "resources" / "icon.ico").exists()


def test_resource_path_resolves_in_development():
    icon = resource_path("resources/icon.ico")
    assert icon.exists()
    assert str(icon).startswith(str(PROJECT_ROOT))


def test_database_path_is_user_data(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATA_DIR_ENV_VAR, str(tmp_path))
    db = paths.database_path()
    assert db == tmp_path / "cyberglossary.db"
    # Must never be inside the source/executable directory.
    assert not str(db).startswith(str(PROJECT_ROOT))
