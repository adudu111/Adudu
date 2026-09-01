"""Domain data shapes (plain dataclasses, not ORM entities).

These mirror the SQLite schema and are produced/consumed by the repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string (used for all timestamps)."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Profile:
    """A top-level knowledge scope (e.g. "Cyber Security")."""

    id: int
    name: str
    description: str
    color: str | None
    sort_order: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Term:
    """A named entry within a profile (e.g. "LDAP")."""

    id: int
    profile_id: int
    term: str
    full_name: str
    sort_order: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Section:
    """A user-defined, ordered block within a term (e.g. "Ports", "AS-REQ", "My Notes")."""

    id: int
    term_id: int
    title: str
    content: str
    sort_order: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Alias:
    """A user-defined alternate name or misspelling for a term."""

    id: int
    term_id: int
    alias: str
    created_at: str


@dataclass(frozen=True)
class Template:
    """A per-profile, named, ordered set of section definitions."""

    id: int
    profile_id: int
    name: str
    description: str
    sort_order: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TemplateSection:
    """A single section definition inside a template (title + optional hint)."""

    id: int
    template_id: int
    title: str
    placeholder: str
    sort_order: int


@dataclass(frozen=True)
class Category:
    """An optional grouping of terms within a profile."""

    id: int
    profile_id: int
    name: str
    sort_order: int


@dataclass(frozen=True)
class Tag:
    """An optional label attached to terms within a profile."""

    id: int
    profile_id: int
    name: str
