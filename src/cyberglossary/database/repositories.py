"""SQLite repositories (thin data-access layer).

Repositories receive an open ``sqlite3.Connection`` and own their writes (each method
commits its own change). Transaction coordination across repositories is deferred to the
phase that introduces multi-table writes (terms + sections + FTS).

Domain errors are raised here so the service layer never has to inspect ``sqlite3``
error codes.
"""

from __future__ import annotations

import sqlite3

from cyberglossary.database import fts
from cyberglossary.database.models import (
    Alias,
    Category,
    Profile,
    Section,
    Tag,
    Template,
    TemplateSection,
    Term,
    utcnow,
)


class DomainError(Exception):
    """Base class for all CyberGlossary domain errors."""


class ProfileError(DomainError):
    """Base class for profile-related domain errors."""


class ProfileNotFoundError(ProfileError):
    """Raised when a requested profile does not exist."""


class DuplicateProfileNameError(ProfileError):
    """Raised when a profile name would violate per-profile uniqueness."""

    def __init__(self, name: str):
        super().__init__(f'A profile named "{name}" already exists.')
        self.name = name


class TermError(DomainError):
    """Base class for term-related domain errors."""


class TermNotFoundError(TermError):
    """Raised when a requested term does not exist."""


class DuplicateTermNameError(TermError):
    """Raised when a term name would violate per-profile uniqueness."""

    def __init__(self, name: str):
        super().__init__(f'A term named "{name}" already exists in this profile.')
        self.name = name


class SectionError(DomainError):
    """Base class for section-related domain errors."""


class SectionNotFoundError(SectionError):
    """Raised when a requested section does not exist."""


class AliasError(DomainError):
    """Base class for alias-related domain errors."""


class AliasNotFoundError(AliasError):
    """Raised when a requested alias does not exist."""


class DuplicateAliasError(AliasError):
    """Raised when an alias would violate per-term uniqueness."""

    def __init__(self, alias: str):
        super().__init__(f'The alias "{alias}" already exists for this term.')
        self.alias = alias


class TemplateError(DomainError):
    """Base class for template-related domain errors."""


class TemplateNotFoundError(TemplateError):
    """Raised when a requested template does not exist."""


class DuplicateTemplateNameError(TemplateError):
    """Raised when a template name would violate per-profile uniqueness."""


class TemplateSectionError(DomainError):
    """Base class for template-section-related domain errors."""


class TemplateSectionNotFoundError(TemplateSectionError):
    """Raised when a requested template section does not exist."""


class CategoryError(DomainError):
    """Base class for category-related domain errors."""


class CategoryNotFoundError(CategoryError):
    """Raised when a requested category does not exist."""


class DuplicateCategoryNameError(CategoryError):
    """Raised when a category name would violate per-profile uniqueness."""

    def __init__(self, name: str):
        super().__init__(f'A category named "{name}" already exists in this profile.')
        self.name = name


class TagError(DomainError):
    """Base class for tag-related domain errors."""


class TagNotFoundError(TagError):
    """Raised when a requested tag does not exist."""


class DuplicateTagNameError(TagError):
    """Raised when a tag name would violate per-profile uniqueness."""


def _profile_from_row(row: sqlite3.Row) -> Profile:
    return Profile(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _term_from_row(row: sqlite3.Row) -> Term:
    return Term(
        id=row["id"],
        profile_id=row["profile_id"],
        term=row["term"],
        full_name=row["full_name"],
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _section_from_row(row: sqlite3.Row) -> Section:
    return Section(
        id=row["id"],
        term_id=row["term_id"],
        title=row["title"],
        content=row["content"],
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _alias_from_row(row: sqlite3.Row) -> Alias:
    return Alias(
        id=row["id"],
        term_id=row["term_id"],
        alias=row["alias"],
        created_at=row["created_at"],
    )


def _template_from_row(row: sqlite3.Row) -> Template:
    return Template(
        id=row["id"],
        profile_id=row["profile_id"],
        name=row["name"],
        description=row["description"],
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _template_section_from_row(row: sqlite3.Row) -> TemplateSection:
    return TemplateSection(
        id=row["id"],
        template_id=row["template_id"],
        title=row["title"],
        placeholder=row["placeholder"],
        sort_order=row["sort_order"],
    )


def _category_from_row(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"],
        profile_id=row["profile_id"],
        name=row["name"],
        sort_order=row["sort_order"],
    )


def _tag_from_row(row: sqlite3.Row) -> Tag:
    return Tag(
        id=row["id"],
        profile_id=row["profile_id"],
        name=row["name"],
    )


class SettingsRepository:
    """Key/value access to the ``settings`` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else default

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self._conn.commit()


class ProfileRepository:
    """CRUD + ordering for ``profiles``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _next_sort_order(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM profiles"
        ).fetchone()
        return row[0]

    def create(self, name: str, description: str = "", color: str | None = None) -> Profile:
        now = utcnow()
        sort_order = self._next_sort_order()
        try:
            cur = self._conn.execute(
                "INSERT INTO profiles (name, description, color, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, color, sort_order, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileNameError(name) from exc
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, profile_id: int) -> Profile | None:
        row = self._conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return _profile_from_row(row) if row is not None else None

    def get_by_name(self, name: str) -> Profile | None:
        row = self._conn.execute(
            "SELECT * FROM profiles WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return _profile_from_row(row) if row is not None else None

    def list_all(self) -> list[Profile]:
        rows = self._conn.execute(
            "SELECT * FROM profiles ORDER BY sort_order, name COLLATE NOCASE"
        ).fetchall()
        return [_profile_from_row(row) for row in rows]

    def rename(self, profile_id: int, name: str) -> Profile:
        if self.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        try:
            self._conn.execute(
                "UPDATE profiles SET name = ?, updated_at = ? WHERE id = ?",
                (name, utcnow(), profile_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileNameError(name) from exc
        self._conn.commit()
        return self.get(profile_id)

    def set_description(self, profile_id: int, description: str) -> Profile:
        if self.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        self._conn.execute(
            "UPDATE profiles SET description = ?, updated_at = ? WHERE id = ?",
            (description, utcnow(), profile_id),
        )
        self._conn.commit()
        return self.get(profile_id)

    def set_color(self, profile_id: int, color: str | None) -> Profile:
        if self.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        self._conn.execute(
            "UPDATE profiles SET color = ?, updated_at = ? WHERE id = ?",
            (color, utcnow(), profile_id),
        )
        self._conn.commit()
        return self.get(profile_id)

    def reorder(self, ordered_ids: list[int]) -> None:
        """Assign sort_order by position in ``ordered_ids`` (0, 1, 2, ...)."""
        for index, profile_id in enumerate(ordered_ids):
            self._conn.execute(
                "UPDATE profiles SET sort_order = ? WHERE id = ?", (index, profile_id)
            )
        self._conn.commit()

    def delete(self, profile_id: int) -> None:
        fts.delete_profile_terms(self._conn, profile_id)
        cur = self._conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        self._conn.commit()
        if cur.rowcount == 0:
            raise ProfileNotFoundError(profile_id)


class TermRepository:
    """CRUD + ordering for ``terms``, plus atomic duplication."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _next_sort_order(self, profile_id: int) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM terms WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        return row[0]

    def create(self, profile_id: int, term: str, full_name: str = "") -> Term:
        now = utcnow()
        sort_order = self._next_sort_order(profile_id)
        try:
            cur = self._conn.execute(
                "INSERT INTO terms (profile_id, term, full_name, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (profile_id, term, full_name, sort_order, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTermNameError(term) from exc
        fts.sync_term(self._conn, cur.lastrowid)
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, term_id: int) -> Term | None:
        row = self._conn.execute(
            "SELECT id, profile_id, term, full_name, sort_order, created_at, updated_at "
            "FROM terms WHERE id = ?",
            (term_id,),
        ).fetchone()
        return _term_from_row(row) if row is not None else None

    def get_by_name(self, profile_id: int, term: str) -> Term | None:
        row = self._conn.execute(
            "SELECT id, profile_id, term, full_name, sort_order, created_at, updated_at "
            "FROM terms WHERE profile_id = ? AND term = ? COLLATE NOCASE",
            (profile_id, term),
        ).fetchone()
        return _term_from_row(row) if row is not None else None

    def list_for_profile(self, profile_id: int) -> list[Term]:
        rows = self._conn.execute(
            "SELECT id, profile_id, term, full_name, sort_order, created_at, updated_at "
            "FROM terms WHERE profile_id = ? ORDER BY sort_order, term COLLATE NOCASE",
            (profile_id,),
        ).fetchall()
        return [_term_from_row(row) for row in rows]

    def rename(self, term_id: int, term: str) -> Term:
        if self.get(term_id) is None:
            raise TermNotFoundError(term_id)
        try:
            self._conn.execute(
                "UPDATE terms SET term = ?, updated_at = ? WHERE id = ?",
                (term, utcnow(), term_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTermNameError(term) from exc
        fts.sync_term(self._conn, term_id)
        self._conn.commit()
        return self.get(term_id)

    def set_full_name(self, term_id: int, full_name: str) -> Term:
        if self.get(term_id) is None:
            raise TermNotFoundError(term_id)
        self._conn.execute(
            "UPDATE terms SET full_name = ?, updated_at = ? WHERE id = ?",
            (full_name, utcnow(), term_id),
        )
        fts.sync_term(self._conn, term_id)
        self._conn.commit()
        return self.get(term_id)

    def reorder(self, profile_id: int, ordered_ids: list[int]) -> None:
        for index, term_id in enumerate(ordered_ids):
            self._conn.execute(
                "UPDATE terms SET sort_order = ? WHERE id = ? AND profile_id = ?",
                (index, term_id, profile_id),
            )
        self._conn.commit()

    def delete(self, term_id: int) -> None:
        cur = self._conn.execute("DELETE FROM terms WHERE id = ?", (term_id,))
        fts.delete_term(self._conn, term_id)
        self._conn.commit()
        if cur.rowcount == 0:
            raise TermNotFoundError(term_id)

    def delete_many(self, term_ids: list[int]) -> None:
        """Delete multiple terms atomically (cascade removes sections/aliases; FTS cleaned)."""
        with self._conn:
            for term_id in term_ids:
                self._conn.execute("DELETE FROM terms WHERE id = ?", (term_id,))
                fts.delete_term(self._conn, term_id)

    def set_category(self, term_id: int, category_id: int | None) -> Term:
        term = self.get(term_id)
        if term is None:
            raise TermNotFoundError(term_id)
        if category_id is not None:
            exists = self._conn.execute(
                "SELECT 1 FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
            if exists is None:
                raise CategoryNotFoundError(category_id)
        self._conn.execute(
            "UPDATE terms SET category_id = ?, updated_at = ? WHERE id = ?",
            (category_id, utcnow(), term_id),
        )
        fts.sync_term(self._conn, term_id)
        self._conn.commit()
        return self.get(term_id)

    def set_tags(self, term_id: int, tag_names: list[str]) -> list[Tag]:
        term = self.get(term_id)
        if term is None:
            raise TermNotFoundError(term_id)
        self._conn.execute("DELETE FROM term_tags WHERE term_id = ?", (term_id,))
        for name in tag_names:
            name = name.strip()
            if not name:
                continue
            row = self._conn.execute(
                "SELECT id FROM tags WHERE profile_id = ? AND name = ? COLLATE NOCASE",
                (term.profile_id, name),
            ).fetchone()
            if row is None:
                cur = self._conn.execute(
                    "INSERT INTO tags (profile_id, name) VALUES (?, ?)",
                    (term.profile_id, name),
                )
                tag_id = cur.lastrowid
            else:
                tag_id = row["id"]
            self._conn.execute(
                "INSERT INTO term_tags (term_id, tag_id) VALUES (?, ?)", (term_id, tag_id)
            )
        fts.sync_term(self._conn, term_id)
        self._conn.commit()
        return self.get_tags(term_id)

    def get_tags(self, term_id: int) -> list[Tag]:
        rows = self._conn.execute(
            "SELECT g.id, g.profile_id, g.name FROM term_tags tt "
            "JOIN tags g ON g.id = tt.tag_id WHERE tt.term_id = ? ORDER BY g.name COLLATE NOCASE",
            (term_id,),
        ).fetchall()
        return [_tag_from_row(row) for row in rows]

    def get_category(self, term_id: int) -> Category | None:
        row = self._conn.execute(
            "SELECT c.id, c.profile_id, c.name, c.sort_order FROM categories c "
            "JOIN terms t ON t.category_id = c.id WHERE t.id = ?",
            (term_id,),
        ).fetchone()
        return _category_from_row(row) if row is not None else None

    def list_by_category(self, category_id: int) -> list[Term]:
        rows = self._conn.execute(
            "SELECT id, profile_id, term, full_name, sort_order, created_at, updated_at "
            "FROM terms WHERE category_id = ? ORDER BY sort_order, term COLLATE NOCASE",
            (category_id,),
        ).fetchall()
        return [_term_from_row(row) for row in rows]

    def count_by_category(self, category_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM terms WHERE category_id = ?", (category_id,)
        ).fetchone()
        return row[0]

    def _next_copy_name(self, source: Term) -> str:
        candidate = f"{source.term} (copy)"
        counter = 2
        while self.get_by_name(source.profile_id, candidate) is not None:
            candidate = f"{source.term} (copy {counter})"
            counter += 1
        return candidate

    def duplicate(self, term_id: int, new_term: str | None = None) -> Term:
        """Copy a term, its sections, and its aliases (atomic).

        The copy lives in the same profile; its name is ``new_term`` or a generated
        ``"<term> (copy)"`` that does not collide with existing terms.
        """
        source = self.get(term_id)
        if source is None:
            raise TermNotFoundError(term_id)

        with self._conn:
            now = utcnow()
            name = new_term or self._next_copy_name(source)
            sort_order = self._next_sort_order(source.profile_id)
            cur = self._conn.execute(
                "INSERT INTO terms (profile_id, term, full_name, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source.profile_id, name, source.full_name, sort_order, now, now),
            )
            new_id = cur.lastrowid

            sections = self._conn.execute(
                "SELECT title, content, sort_order FROM sections "
                "WHERE term_id = ? ORDER BY sort_order, id",
                (source.id,),
            ).fetchall()
            for section in sections:
                self._conn.execute(
                    "INSERT INTO sections (term_id, title, content, sort_order, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (new_id, section["title"], section["content"], section["sort_order"], now, now),
                )

            aliases = self._conn.execute(
                "SELECT alias FROM aliases WHERE term_id = ? ORDER BY id", (source.id,)
            ).fetchall()
            for alias in aliases:
                self._conn.execute(
                    "INSERT INTO aliases (term_id, alias, created_at) VALUES (?, ?, ?)",
                    (new_id, alias["alias"], now),
                )

            fts.sync_term(self._conn, new_id)

        return self.get(new_id)


class SectionRepository:
    """CRUD + ordering for dynamic ``sections``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _next_sort_order(self, term_id: int) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM sections WHERE term_id = ?",
            (term_id,),
        ).fetchone()
        return row[0]

    def add(self, term_id: int, title: str, content: str = "") -> Section:
        now = utcnow()
        sort_order = self._next_sort_order(term_id)
        cur = self._conn.execute(
            "INSERT INTO sections (term_id, title, content, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (term_id, title, content, sort_order, now, now),
        )
        fts.sync_term(self._conn, term_id)
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, section_id: int) -> Section | None:
        row = self._conn.execute(
            "SELECT * FROM sections WHERE id = ?", (section_id,)
        ).fetchone()
        return _section_from_row(row) if row is not None else None

    def list_for_term(self, term_id: int) -> list[Section]:
        rows = self._conn.execute(
            "SELECT * FROM sections WHERE term_id = ? ORDER BY sort_order, id",
            (term_id,),
        ).fetchall()
        return [_section_from_row(row) for row in rows]

    def rename(self, section_id: int, title: str) -> Section:
        section = self.get(section_id)
        if section is None:
            raise SectionNotFoundError(section_id)
        self._conn.execute(
            "UPDATE sections SET title = ?, updated_at = ? WHERE id = ?",
            (title, utcnow(), section_id),
        )
        fts.sync_term(self._conn, section.term_id)
        self._conn.commit()
        return self.get(section_id)

    def set_content(self, section_id: int, content: str) -> Section:
        section = self.get(section_id)
        if section is None:
            raise SectionNotFoundError(section_id)
        self._conn.execute(
            "UPDATE sections SET content = ?, updated_at = ? WHERE id = ?",
            (content, utcnow(), section_id),
        )
        fts.sync_term(self._conn, section.term_id)
        self._conn.commit()
        return self.get(section_id)

    def reorder(self, term_id: int, ordered_ids: list[int]) -> None:
        """Assign sort_order by position in ``ordered_ids`` (atomic)."""
        with self._conn:
            for index, section_id in enumerate(ordered_ids):
                self._conn.execute(
                    "UPDATE sections SET sort_order = ? WHERE id = ? AND term_id = ?",
                    (index, section_id, term_id),
                )
            fts.sync_term(self._conn, term_id)

    def delete(self, section_id: int) -> None:
        section = self.get(section_id)
        if section is None:
            raise SectionNotFoundError(section_id)
        self._conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
        fts.sync_term(self._conn, section.term_id)
        self._conn.commit()


class AliasRepository:
    """Management of user-defined term aliases."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, term_id: int, alias: str) -> Alias:
        try:
            cur = self._conn.execute(
                "INSERT INTO aliases (term_id, alias, created_at) VALUES (?, ?, ?)",
                (term_id, alias, utcnow()),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateAliasError(alias) from exc
        fts.sync_term(self._conn, term_id)
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, alias_id: int) -> Alias | None:
        row = self._conn.execute(
            "SELECT * FROM aliases WHERE id = ?", (alias_id,)
        ).fetchone()
        return _alias_from_row(row) if row is not None else None

    def list_for_term(self, term_id: int) -> list[Alias]:
        rows = self._conn.execute(
            "SELECT * FROM aliases WHERE term_id = ? ORDER BY id", (term_id,)
        ).fetchall()
        return [_alias_from_row(row) for row in rows]

    def delete(self, alias_id: int) -> None:
        alias = self.get(alias_id)
        if alias is None:
            raise AliasNotFoundError(alias_id)
        self._conn.execute("DELETE FROM aliases WHERE id = ?", (alias_id,))
        fts.sync_term(self._conn, alias.term_id)
        self._conn.commit()

    def get_term_id_by_alias(self, profile_id: int, alias: str) -> int | None:
        """Return the term id owning an exact (case-insensitive) alias within a profile."""
        row = self._conn.execute(
            "SELECT a.term_id FROM aliases a JOIN terms t ON t.id = a.term_id "
            "WHERE t.profile_id = ? AND a.alias = ? COLLATE NOCASE",
            (profile_id, alias),
        ).fetchone()
        return row[0] if row is not None else None


class TemplateRepository:
    """CRUD + ordering for ``templates``, plus atomic duplication and application."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _next_sort_order(self, profile_id: int) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM templates WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        return row[0]

    def create(self, profile_id: int, name: str, description: str = "") -> Template:
        now = utcnow()
        sort_order = self._next_sort_order(profile_id)
        try:
            cur = self._conn.execute(
                "INSERT INTO templates (profile_id, name, description, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (profile_id, name, description, sort_order, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTemplateNameError(name) from exc
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, template_id: int) -> Template | None:
        row = self._conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _template_from_row(row) if row is not None else None

    def get_by_name(self, profile_id: int, name: str) -> Template | None:
        row = self._conn.execute(
            "SELECT * FROM templates WHERE profile_id = ? AND name = ? COLLATE NOCASE",
            (profile_id, name),
        ).fetchone()
        return _template_from_row(row) if row is not None else None

    def list_for_profile(self, profile_id: int) -> list[Template]:
        rows = self._conn.execute(
            "SELECT * FROM templates WHERE profile_id = ? ORDER BY sort_order, name COLLATE NOCASE",
            (profile_id,),
        ).fetchall()
        return [_template_from_row(row) for row in rows]

    def rename(self, template_id: int, name: str) -> Template:
        if self.get(template_id) is None:
            raise TemplateNotFoundError(template_id)
        try:
            self._conn.execute(
                "UPDATE templates SET name = ?, updated_at = ? WHERE id = ?",
                (name, utcnow(), template_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTemplateNameError(name) from exc
        self._conn.commit()
        return self.get(template_id)

    def set_description(self, template_id: int, description: str) -> Template:
        if self.get(template_id) is None:
            raise TemplateNotFoundError(template_id)
        self._conn.execute(
            "UPDATE templates SET description = ?, updated_at = ? WHERE id = ?",
            (description, utcnow(), template_id),
        )
        self._conn.commit()
        return self.get(template_id)

    def reorder(self, profile_id: int, ordered_ids: list[int]) -> None:
        for index, template_id in enumerate(ordered_ids):
            self._conn.execute(
                "UPDATE templates SET sort_order = ? WHERE id = ? AND profile_id = ?",
                (index, template_id, profile_id),
            )
        self._conn.commit()

    def delete(self, template_id: int) -> None:
        cur = self._conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        self._conn.commit()
        if cur.rowcount == 0:
            raise TemplateNotFoundError(template_id)

    def _next_copy_name(self, source: Template) -> str:
        candidate = f"{source.name} (copy)"
        counter = 2
        while self.get_by_name(source.profile_id, candidate) is not None:
            candidate = f"{source.name} (copy {counter})"
            counter += 1
        return candidate

    def duplicate(self, template_id: int, new_name: str | None = None) -> Template:
        """Copy a template and its template_sections (atomic)."""
        source = self.get(template_id)
        if source is None:
            raise TemplateNotFoundError(template_id)

        with self._conn:
            now = utcnow()
            name = new_name or self._next_copy_name(source)
            sort_order = self._next_sort_order(source.profile_id)
            cur = self._conn.execute(
                "INSERT INTO templates (profile_id, name, description, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source.profile_id, name, source.description, sort_order, now, now),
            )
            new_id = cur.lastrowid

            sections = self._conn.execute(
                "SELECT title, placeholder, sort_order FROM template_sections "
                "WHERE template_id = ? ORDER BY sort_order, id",
                (source.id,),
            ).fetchall()
            for section in sections:
                self._conn.execute(
                    "INSERT INTO template_sections (template_id, title, placeholder, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    (new_id, section["title"], section["placeholder"], section["sort_order"]),
                )

        return self.get(new_id)

    def apply(self, template_id: int, term: str, full_name: str = "") -> Term:
        """Create a new term in the template's profile from its sections (atomic).

        Materializes each template section into an independent ``sections`` row with empty
        content. The placeholder is a UI hint only and is not copied into content.
        """
        template = self.get(template_id)
        if template is None:
            raise TemplateNotFoundError(template_id)

        sections = self._conn.execute(
            "SELECT title FROM template_sections WHERE template_id = ? ORDER BY sort_order, id",
            (template_id,),
        ).fetchall()

        with self._conn:
            now = utcnow()
            term_sort = self._conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM terms WHERE profile_id = ?",
                (template.profile_id,),
            ).fetchone()[0]
            try:
                cur = self._conn.execute(
                    "INSERT INTO terms (profile_id, term, full_name, sort_order, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (template.profile_id, term, full_name, term_sort, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateTermNameError(term) from exc
            new_term_id = cur.lastrowid

            for index, section in enumerate(sections):
                self._conn.execute(
                    "INSERT INTO sections (term_id, title, content, sort_order, created_at, updated_at) "
                    "VALUES (?, ?, '', ?, ?, ?)",
                    (new_term_id, section["title"], index, now, now),
                )

            fts.sync_term(self._conn, new_term_id)

        row = self._conn.execute(
            "SELECT id, profile_id, term, full_name, sort_order, created_at, updated_at "
            "FROM terms WHERE id = ?",
            (new_term_id,),
        ).fetchone()
        return _term_from_row(row)


class TemplateSectionRepository:
    """CRUD + ordering for ``template_sections``."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _next_sort_order(self, template_id: int) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM template_sections WHERE template_id = ?",
            (template_id,),
        ).fetchone()
        return row[0]

    def add(self, template_id: int, title: str, placeholder: str = "") -> TemplateSection:
        sort_order = self._next_sort_order(template_id)
        cur = self._conn.execute(
            "INSERT INTO template_sections (template_id, title, placeholder, sort_order) "
            "VALUES (?, ?, ?, ?)",
            (template_id, title, placeholder, sort_order),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, section_id: int) -> TemplateSection | None:
        row = self._conn.execute(
            "SELECT * FROM template_sections WHERE id = ?", (section_id,)
        ).fetchone()
        return _template_section_from_row(row) if row is not None else None

    def list_for_template(self, template_id: int) -> list[TemplateSection]:
        rows = self._conn.execute(
            "SELECT * FROM template_sections WHERE template_id = ? ORDER BY sort_order, id",
            (template_id,),
        ).fetchall()
        return [_template_section_from_row(row) for row in rows]

    def set_title(self, section_id: int, title: str) -> TemplateSection:
        if self.get(section_id) is None:
            raise TemplateSectionNotFoundError(section_id)
        self._conn.execute(
            "UPDATE template_sections SET title = ? WHERE id = ?", (title, section_id)
        )
        self._conn.commit()
        return self.get(section_id)

    def set_placeholder(self, section_id: int, placeholder: str) -> TemplateSection:
        if self.get(section_id) is None:
            raise TemplateSectionNotFoundError(section_id)
        self._conn.execute(
            "UPDATE template_sections SET placeholder = ? WHERE id = ?",
            (placeholder, section_id),
        )
        self._conn.commit()
        return self.get(section_id)

    def reorder(self, template_id: int, ordered_ids: list[int]) -> None:
        with self._conn:
            for index, section_id in enumerate(ordered_ids):
                self._conn.execute(
                    "UPDATE template_sections SET sort_order = ? WHERE id = ? AND template_id = ?",
                    (index, section_id, template_id),
                )

    def delete(self, section_id: int) -> None:
        cur = self._conn.execute(
            "DELETE FROM template_sections WHERE id = ?", (section_id,)
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise TemplateSectionNotFoundError(section_id)


class CategoryRepository:
    """CRUD for ``categories`` (per profile)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _next_sort_order(self, profile_id: int) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM categories WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        return row[0]

    def create(self, profile_id: int, name: str) -> Category:
        sort_order = self._next_sort_order(profile_id)
        try:
            cur = self._conn.execute(
                "INSERT INTO categories (profile_id, name, sort_order) VALUES (?, ?, ?)",
                (profile_id, name, sort_order),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCategoryNameError(name) from exc
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, category_id: int) -> Category | None:
        row = self._conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        return _category_from_row(row) if row is not None else None

    def get_by_name(self, profile_id: int, name: str) -> Category | None:
        row = self._conn.execute(
            "SELECT * FROM categories WHERE profile_id = ? AND name = ? COLLATE NOCASE",
            (profile_id, name),
        ).fetchone()
        return _category_from_row(row) if row is not None else None

    def list_for_profile(self, profile_id: int) -> list[Category]:
        rows = self._conn.execute(
            "SELECT * FROM categories WHERE profile_id = ? ORDER BY sort_order, name COLLATE NOCASE",
            (profile_id,),
        ).fetchall()
        return [_category_from_row(row) for row in rows]

    def rename(self, category_id: int, name: str) -> Category:
        if self.get(category_id) is None:
            raise CategoryNotFoundError(category_id)
        try:
            self._conn.execute(
                "UPDATE categories SET name = ? WHERE id = ?", (name, category_id)
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCategoryNameError(name) from exc
        fts.sync_terms_for_category(self._conn, category_id)
        self._conn.commit()
        return self.get(category_id)

    def delete(self, category_id: int) -> None:
        if self.get(category_id) is None:
            raise CategoryNotFoundError(category_id)
        term_ids = [
            row[0]
            for row in self._conn.execute(
                "SELECT id FROM terms WHERE category_id = ?", (category_id,)
            ).fetchall()
        ]
        self._conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        for term_id in term_ids:
            fts.sync_term(self._conn, term_id)
        self._conn.commit()

    def reorder(self, profile_id: int, ordered_ids: list[int]) -> None:
        """Assign sort_order by position in ``ordered_ids`` (0, 1, 2, ...)."""
        for index, category_id in enumerate(ordered_ids):
            self._conn.execute(
                "UPDATE categories SET sort_order = ? WHERE id = ? AND profile_id = ?",
                (index, category_id, profile_id),
            )
        self._conn.commit()


class TagRepository:
    """CRUD for ``tags`` (per profile)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, profile_id: int, name: str) -> Tag:
        try:
            cur = self._conn.execute(
                "INSERT INTO tags (profile_id, name) VALUES (?, ?)", (profile_id, name)
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateTagNameError(name) from exc
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, tag_id: int) -> Tag | None:
        row = self._conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return _tag_from_row(row) if row is not None else None

    def get_by_name(self, profile_id: int, name: str) -> Tag | None:
        row = self._conn.execute(
            "SELECT * FROM tags WHERE profile_id = ? AND name = ? COLLATE NOCASE",
            (profile_id, name),
        ).fetchone()
        return _tag_from_row(row) if row is not None else None

    def list_for_profile(self, profile_id: int) -> list[Tag]:
        rows = self._conn.execute(
            "SELECT * FROM tags WHERE profile_id = ? ORDER BY name COLLATE NOCASE",
            (profile_id,),
        ).fetchall()
        return [_tag_from_row(row) for row in rows]

    def rename(self, tag_id: int, name: str) -> Tag:
        if self.get(tag_id) is None:
            raise TagNotFoundError(tag_id)
        try:
            self._conn.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
        except sqlite3.IntegrityError as exc:
            raise DuplicateTagNameError(name) from exc
        fts.sync_terms_for_tag(self._conn, tag_id)
        self._conn.commit()
        return self.get(tag_id)

    def delete(self, tag_id: int) -> None:
        if self.get(tag_id) is None:
            raise TagNotFoundError(tag_id)
        term_ids = [
            row[0]
            for row in self._conn.execute(
                "SELECT term_id FROM term_tags WHERE tag_id = ?", (tag_id,)
            ).fetchall()
        ]
        self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        for term_id in term_ids:
            fts.sync_term(self._conn, term_id)
        self._conn.commit()


class SearchRepository:
    """Full-text search over ``terms_fts`` (FTS5)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def search(self, match_query: str, profile_id: int | None) -> list[sqlite3.Row]:
        sql = (
            "SELECT t.id AS term_id, t.term, t.full_name, t.profile_id, "
            "       p.name AS profile_name, terms_fts.category, "
            "       snippet(terms_fts, 5, '[[', ']]', '...', 15) AS snippet "
            "FROM terms_fts "
            "JOIN terms t ON t.id = terms_fts.rowid "
            "JOIN profiles p ON p.id = t.profile_id "
            "WHERE terms_fts MATCH ?"
        )
        params: list[object] = [match_query]
        if profile_id is not None:
            sql += " AND t.profile_id = ?"
            params.append(profile_id)
        sql += " ORDER BY rank LIMIT 200"
        return self._conn.execute(sql, params).fetchall()

    def search_rowids(self, match_query: str, profile_id: int | None) -> set[int]:
        if profile_id is not None:
            sql = (
                "SELECT terms_fts.rowid FROM terms_fts "
                "JOIN terms t ON t.id = terms_fts.rowid "
                "WHERE terms_fts MATCH ? AND t.profile_id = ?"
            )
            params: list[object] = [match_query, profile_id]
        else:
            sql = "SELECT terms_fts.rowid FROM terms_fts WHERE terms_fts MATCH ?"
            params = [match_query]
        return {row[0] for row in self._conn.execute(sql, params).fetchall()}

    def fetch_terms(self, profile_id: int | None) -> list[sqlite3.Row]:
        sql = (
            "SELECT t.id AS term_id, t.term, t.full_name, t.profile_id, "
            "       p.name AS profile_name, "
            "       (SELECT category FROM terms_fts WHERE rowid = t.id) AS category, "
            "       NULL AS snippet "
            "FROM terms t JOIN profiles p ON p.id = t.profile_id"
        )
        params: list[object] = []
        if profile_id is not None:
            sql += " WHERE t.profile_id = ?"
            params.append(profile_id)
        sql += " ORDER BY t.sort_order, t.term COLLATE NOCASE"
        return self._conn.execute(sql, params).fetchall()
