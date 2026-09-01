"""Profile import from JSON (merge or replace), with strict validation and atomicity.

Validation is pure (no DB writes). Execution runs inside a single transaction, so any
failure rolls back completely. Imported ids are treated as in-file references only and
are remapped to new local ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from cyberglossary.database import fts
from cyberglossary.database.models import utcnow

SCHEMA_VERSION = 1
_MERGE = "merge"
_REPLACE = "replace"
_VALID_MODES = (_MERGE, _REPLACE)


class ImportError(Exception):
    """Base class for import errors."""


class ImportValidationError(ImportError):
    """Raised when imported data fails validation (no DB changes are made)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass
class ImportResult:
    profile_id: int
    profile_name: str
    terms_imported: int
    terms_skipped: list[str] = field(default_factory=list)
    replaced: bool = False


def parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportValidationError([f"Invalid JSON: {exc}"]) from exc
    if not isinstance(data, dict):
        raise ImportValidationError(["Top-level JSON must be an object"])
    return data


def validate_import(data: dict) -> dict:
    """Validate and normalize the import document, raising on any problem."""
    if not isinstance(data, dict):
        raise ImportValidationError(["Top-level JSON must be an object"])
    errors: list[str] = []

    version = data.get("schema_version")
    if not isinstance(version, int):
        errors.append("schema_version must be an integer")
    elif version < 1 or version > SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version {version} (supported: {SCHEMA_VERSION})")

    profile = data.get("profile")
    if not isinstance(profile, dict):
        errors.append("profile must be an object")
    elif not isinstance(profile.get("name"), str) or not profile.get("name", "").strip():
        errors.append("profile.name must be a non-empty string")

    categories = data.get("categories")
    tags = data.get("tags")
    templates = data.get("templates")
    terms = data.get("terms")
    for key, value in (
        ("categories", categories),
        ("tags", tags),
        ("templates", templates),
        ("terms", terms),
    ):
        if not isinstance(value, list):
            errors.append(f"{key} must be a list")

    category_ids = _check_named_entities(categories or [], "categories", errors)
    tag_ids = _check_named_entities(tags or [], "tags", errors)

    if isinstance(templates, list):
        _check_templates(templates, errors)

    if isinstance(terms, list):
        _check_terms(terms, category_ids, tag_ids, errors)

    if errors:
        raise ImportValidationError(errors)
    return data


def _check_named_entities(items, label: str, errors: list[str]) -> set:
    seen_ids: set = set()
    seen_names: set = set()
    ids: set = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, int):
            errors.append(f"{label}[{index}].id must be an integer")
        elif item_id in seen_ids:
            errors.append(f"{label} has a duplicate id {item_id}")
        else:
            seen_ids.add(item_id)
            ids.add(item_id)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label}[{index}].name must be a non-empty string")
        else:
            key = name.strip().lower()
            if key in seen_names:
                errors.append(f"{label} has a duplicate name {name!r}")
            seen_names.add(key)
    return ids


def _check_templates(templates: list, errors: list[str]) -> None:
    seen_ids: set = set()
    seen_names: set = set()
    for index, template in enumerate(templates):
        if not isinstance(template, dict):
            errors.append(f"templates[{index}] must be an object")
            continue
        item_id = template.get("id")
        if not isinstance(item_id, int):
            errors.append(f"templates[{index}].id must be an integer")
        elif item_id in seen_ids:
            errors.append(f"templates has a duplicate id {item_id}")
        else:
            seen_ids.add(item_id)
        name = template.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"templates[{index}].name must be a non-empty string")
        else:
            key = name.strip().lower()
            if key in seen_names:
                errors.append(f"templates has a duplicate name {name!r}")
            seen_names.add(key)
        sections = template.get("sections", [])
        if not isinstance(sections, list):
            errors.append(f"templates[{index}].sections must be a list")
        else:
            _check_sections(sections, f"templates[{index}].sections", errors)


def _check_terms(terms: list, category_ids: set, tag_ids: set, errors: list[str]) -> None:
    seen_ids: set = set()
    seen_names: set = set()
    for index, term in enumerate(terms):
        if not isinstance(term, dict):
            errors.append(f"terms[{index}] must be an object")
            continue
        item_id = term.get("id")
        if not isinstance(item_id, int):
            errors.append(f"terms[{index}].id must be an integer")
        elif item_id in seen_ids:
            errors.append(f"terms has a duplicate id {item_id}")
        else:
            seen_ids.add(item_id)
        name = term.get("term")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"terms[{index}].term must be a non-empty string")
        else:
            key = name.strip().lower()
            if key in seen_names:
                errors.append(f"terms has a duplicate term {name!r}")
            seen_names.add(key)

        category_id = term.get("category_id")
        if category_id is not None and category_id not in category_ids:
            errors.append(f"terms[{index}].category_id references an unknown category")

        term_tag_ids = term.get("tag_ids", [])
        if not isinstance(term_tag_ids, list):
            errors.append(f"terms[{index}].tag_ids must be a list")
        else:
            for tag_id in term_tag_ids:
                if tag_id not in tag_ids:
                    errors.append(f"terms[{index}].tag_ids references an unknown tag")

        aliases = term.get("aliases", [])
        if not isinstance(aliases, list):
            errors.append(f"terms[{index}].aliases must be a list")
        else:
            seen_aliases: set = set()
            for alias in aliases:
                if not isinstance(alias, str) or not alias.strip():
                    errors.append(f"terms[{index}].aliases must contain non-empty strings")
                else:
                    key = alias.strip().lower()
                    if key in seen_aliases:
                        errors.append(f"terms[{index}].aliases has a duplicate {alias!r}")
                    seen_aliases.add(key)

        sections = term.get("sections", [])
        if not isinstance(sections, list):
            errors.append(f"terms[{index}].sections must be a list")
        else:
            _check_sections(sections, f"terms[{index}].sections", errors)


def _check_sections(sections: list, label: str, errors: list[str]) -> None:
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        title = section.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{label}[{index}].title must be a non-empty string")
        order = section.get("sort_order", 0)
        if not isinstance(order, int) or order < 0:
            errors.append(f"{label}[{index}].sort_order must be a non-negative integer")


def import_profile(conn, data: dict, mode: str = _MERGE) -> ImportResult:
    """Import a validated profile document atomically."""
    if mode not in _VALID_MODES:
        raise ImportError(f"Invalid import mode {mode!r}")
    validated = validate_import(data)
    with conn:
        return _execute(conn, validated, mode)


def _execute(conn, data: dict, mode: str) -> ImportResult:
    profile = data["profile"]
    name = profile["name"].strip()
    description = profile.get("description") or ""
    color = profile.get("color")

    replaced = False
    existing = conn.execute(
        "SELECT id FROM profiles WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if existing is not None and mode == _REPLACE:
        fts.delete_profile_terms(conn, existing["id"])
        conn.execute("DELETE FROM profiles WHERE id = ?", (existing["id"],))
        existing = None
        replaced = True

    if existing is not None:
        profile_id = existing["id"]
    else:
        now = utcnow()
        sort_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM profiles"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO profiles (name, description, color, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, description, color, sort_order, now, now),
        )
        profile_id = cur.lastrowid

    category_map = _import_categories(conn, profile_id, data.get("categories", []), mode)
    tag_map = _import_tags(conn, profile_id, data.get("tags", []), mode)
    _import_templates(conn, profile_id, data.get("templates", []), mode)

    terms_imported = 0
    skipped: list[str] = []
    now = utcnow()
    for index, term in enumerate(data.get("terms", [])):
        existing_term = conn.execute(
            "SELECT id FROM terms WHERE profile_id = ? AND term = ? COLLATE NOCASE",
            (profile_id, term["term"]),
        ).fetchone()
        if existing_term is not None and mode == _MERGE:
            skipped.append(term["term"])
            continue

        category_id = category_map.get(term.get("category_id"))
        cur = conn.execute(
            "INSERT INTO terms (profile_id, term, full_name, category_id, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (profile_id, term["term"], term.get("full_name") or "", category_id, index, now, now),
        )
        term_id = cur.lastrowid

        for order, section in enumerate(term.get("sections", [])):
            conn.execute(
                "INSERT INTO sections (term_id, title, content, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (term_id, section["title"], section.get("content") or "", order, now, now),
            )
        for alias in term.get("aliases", []):
            conn.execute(
                "INSERT INTO aliases (term_id, alias, created_at) VALUES (?, ?, ?)",
                (term_id, alias, now),
            )
        for tag_id in term.get("tag_ids", []):
            new_tag_id = tag_map.get(tag_id)
            if new_tag_id is not None:
                conn.execute(
                    "INSERT INTO term_tags (term_id, tag_id) VALUES (?, ?)",
                    (term_id, new_tag_id),
                )
        fts.sync_term(conn, term_id)
        terms_imported += 1

    return ImportResult(
        profile_id=profile_id,
        profile_name=name,
        terms_imported=terms_imported,
        terms_skipped=skipped,
        replaced=replaced,
    )


def _import_categories(conn, profile_id: int, categories: list, mode: str) -> dict:
    mapping: dict = {}
    for index, category in enumerate(categories):
        existing = conn.execute(
            "SELECT id FROM categories WHERE profile_id = ? AND name = ? COLLATE NOCASE",
            (profile_id, category["name"]),
        ).fetchone()
        if existing is not None and mode == _MERGE:
            mapping[category["id"]] = existing["id"]
            continue
        cur = conn.execute(
            "INSERT INTO categories (profile_id, name, sort_order) VALUES (?, ?, ?)",
            (profile_id, category["name"], index),
        )
        mapping[category["id"]] = cur.lastrowid
    return mapping


def _import_tags(conn, profile_id: int, tags: list, mode: str) -> dict:
    mapping: dict = {}
    for tag in tags:
        existing = conn.execute(
            "SELECT id FROM tags WHERE profile_id = ? AND name = ? COLLATE NOCASE",
            (profile_id, tag["name"]),
        ).fetchone()
        if existing is not None and mode == _MERGE:
            mapping[tag["id"]] = existing["id"]
            continue
        cur = conn.execute(
            "INSERT INTO tags (profile_id, name) VALUES (?, ?)", (profile_id, tag["name"])
        )
        mapping[tag["id"]] = cur.lastrowid
    return mapping


def _import_templates(conn, profile_id: int, templates: list, mode: str) -> None:
    now = utcnow()
    for index, template in enumerate(templates):
        existing = conn.execute(
            "SELECT id FROM templates WHERE profile_id = ? AND name = ? COLLATE NOCASE",
            (profile_id, template["name"]),
        ).fetchone()
        if existing is not None and mode == _MERGE:
            continue
        cur = conn.execute(
            "INSERT INTO templates (profile_id, name, description, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, template["name"], template.get("description") or "", index, now, now),
        )
        template_id = cur.lastrowid
        for order, section in enumerate(template.get("sections", [])):
            conn.execute(
                "INSERT INTO template_sections (template_id, title, placeholder, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (template_id, section["title"], section.get("placeholder") or "", order),
            )
