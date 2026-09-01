"""Shared pytest fixtures for CyberGlossary tests."""

from __future__ import annotations

import os
import sqlite3

import pytest

# Ensure Qt runs headless during tests; must be set before QApplication is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
from cyberglossary.services.lookup_service import LookupService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.services.search_service import SearchService
from cyberglossary.services.template_service import TemplateService


@pytest.fixture
def data_dir(tmp_path, monkeypatch) -> object:
    """Point the app data directory at a per-test temporary directory."""
    monkeypatch.setenv(paths.DATA_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


@pytest.fixture
def db_path(data_dir):
    return data_dir / "test.db"


@pytest.fixture
def conn(db_path) -> sqlite3.Connection:
    """A migrated SQLite connection backed by a temporary file."""
    c = connection.connect(db_path)
    migrations.migrate(c)
    yield c
    c.close()


@pytest.fixture
def profile_service(conn) -> ProfileService:
    return ProfileService(ProfileRepository(conn), SettingsRepository(conn))


@pytest.fixture
def glossary_service(conn) -> GlossaryService:
    return GlossaryService(
        ProfileRepository(conn),
        TermRepository(conn),
        SectionRepository(conn),
        AliasRepository(conn),
        CategoryRepository(conn),
        TagRepository(conn),
    )


@pytest.fixture
def search_service(conn) -> SearchService:
    return SearchService(SearchRepository(conn))


@pytest.fixture
def lookup_service(profile_service, glossary_service, search_service) -> LookupService:
    return LookupService(lambda: None, profile_service, glossary_service, search_service)


@pytest.fixture
def template_service(conn) -> TemplateService:
    return TemplateService(
        ProfileRepository(conn),
        TemplateRepository(conn),
        TemplateSectionRepository(conn),
    )


@pytest.fixture(scope="session")
def qapp():
    """A single shared QApplication for Qt widget tests (offscreen)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, profile_service, glossary_service, search_service):
    """A MainWindow with explicit cleanup (avoids PySide6 GC crashes between tests)."""
    from cyberglossary.ui.main_window import MainWindow

    w = MainWindow(profile_service, glossary_service, search_service)
    yield w
    w.deleteLater()
    qapp.processEvents()
