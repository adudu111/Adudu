"""Glossary business logic: terms, dynamic sections, and aliases.

Contains no UI or SQL. All persistence is delegated to repositories; validation and
orchestration live here. Sections are fully dynamic — this module never references any
specific section title.
"""

from __future__ import annotations

from cyberglossary.database.models import Alias, Category, Section, Tag, Term
from cyberglossary.database.repositories import (
    AliasRepository,
    CategoryRepository,
    ProfileNotFoundError,
    ProfileRepository,
    SectionRepository,
    TagRepository,
    TermNotFoundError,
    TermRepository,
)


class GlossaryService:
    def __init__(
        self,
        profiles: ProfileRepository,
        terms: TermRepository,
        sections: SectionRepository,
        aliases: AliasRepository,
        categories: CategoryRepository,
        tags: TagRepository,
    ) -> None:
        self._profiles = profiles
        self._terms = terms
        self._sections = sections
        self._aliases = aliases
        self._categories = categories
        self._tags = tags

    # --- terms ------------------------------------------------------------

    def create_term(self, profile_id: int, term: str, full_name: str = "") -> Term:
        term = term.strip()
        if not term:
            raise ValueError("Term name must not be empty.")
        if self._profiles.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        return self._terms.create(profile_id, term, full_name)

    def get_term(self, term_id: int) -> Term | None:
        return self._terms.get(term_id)

    def get_term_by_name(self, profile_id: int, name: str) -> Term | None:
        return self._terms.get_by_name(profile_id, name)

    def find_term_by_alias(self, profile_id: int, alias: str) -> Term | None:
        term_id = self._aliases.get_term_id_by_alias(profile_id, alias)
        if term_id is None:
            return None
        return self._terms.get(term_id)

    def list_terms(self, profile_id: int) -> list[Term]:
        return self._terms.list_for_profile(profile_id)

    def rename_term(self, term_id: int, term: str) -> Term:
        term = term.strip()
        if not term:
            raise ValueError("Term name must not be empty.")
        return self._terms.rename(term_id, term)

    def set_full_name(self, term_id: int, full_name: str) -> Term:
        return self._terms.set_full_name(term_id, full_name)

    def reorder_terms(self, profile_id: int, ordered_ids: list[int]) -> None:
        self._terms.reorder(profile_id, ordered_ids)

    def delete_term(self, term_id: int) -> None:
        self._terms.delete(term_id)

    def delete_terms(self, term_ids: list[int]) -> None:
        if term_ids:
            self._terms.delete_many(term_ids)

    def duplicate_term(self, term_id: int, new_term: str | None = None) -> Term:
        if new_term is not None:
            new_term = new_term.strip()
            if not new_term:
                raise ValueError("Term name must not be empty.")
        return self._terms.duplicate(term_id, new_term)

    # --- sections ---------------------------------------------------------

    def add_section(self, term_id: int, title: str, content: str = "") -> Section:
        title = title.strip()
        if not title:
            raise ValueError("Section title must not be empty.")
        if self._terms.get(term_id) is None:
            raise TermNotFoundError(term_id)
        return self._sections.add(term_id, title, content)

    def list_sections(self, term_id: int) -> list[Section]:
        return self._sections.list_for_term(term_id)

    def rename_section(self, section_id: int, title: str) -> Section:
        title = title.strip()
        if not title:
            raise ValueError("Section title must not be empty.")
        return self._sections.rename(section_id, title)

    def set_section_content(self, section_id: int, content: str) -> Section:
        return self._sections.set_content(section_id, content)

    def reorder_sections(self, term_id: int, ordered_ids: list[int]) -> None:
        self._sections.reorder(term_id, ordered_ids)

    def delete_section(self, section_id: int) -> None:
        self._sections.delete(section_id)

    # --- aliases ----------------------------------------------------------

    def add_alias(self, term_id: int, alias: str) -> Alias:
        alias = alias.strip()
        if not alias:
            raise ValueError("Alias must not be empty.")
        if self._terms.get(term_id) is None:
            raise TermNotFoundError(term_id)
        return self._aliases.add(term_id, alias)

    def list_aliases(self, term_id: int) -> list[Alias]:
        return self._aliases.list_for_term(term_id)

    def delete_alias(self, alias_id: int) -> None:
        self._aliases.delete(alias_id)

    # --- category / tags --------------------------------------------------

    def create_category(self, profile_id: int, name: str) -> Category:
        name = name.strip()
        if not name:
            raise ValueError("Category name must not be empty.")
        if self._profiles.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        return self._categories.create(profile_id, name)

    def list_categories(self, profile_id: int) -> list[Category]:
        return self._categories.list_for_profile(profile_id)

    def rename_category(self, category_id: int, name: str) -> Category:
        name = name.strip()
        if not name:
            raise ValueError("Category name must not be empty.")
        return self._categories.rename(category_id, name)

    def delete_category(self, category_id: int) -> None:
        self._categories.delete(category_id)

    def reorder_categories(self, profile_id: int, ordered_ids: list[int]) -> None:
        self._categories.reorder(profile_id, ordered_ids)

    def list_terms_by_category(self, category_id: int) -> list[Term]:
        return self._terms.list_by_category(category_id)

    def count_terms_by_category(self, category_id: int) -> int:
        return self._terms.count_by_category(category_id)

    def set_term_category(self, term_id: int, category_id: int | None) -> Term:
        return self._terms.set_category(term_id, category_id)

    def get_term_category(self, term_id: int) -> Category | None:
        return self._terms.get_category(term_id)

    def set_term_tags(self, term_id: int, tag_names: list[str]) -> list[Tag]:
        return self._terms.set_tags(term_id, tag_names)

    def get_term_tags(self, term_id: int) -> list[Tag]:
        return self._terms.get_tags(term_id)

    def create_tag(self, profile_id: int, name: str) -> Tag:
        name = name.strip()
        if not name:
            raise ValueError("Tag name must not be empty.")
        if self._profiles.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        return self._tags.create(profile_id, name)

    def list_tags(self, profile_id: int) -> list[Tag]:
        return self._tags.list_for_profile(profile_id)

    def rename_tag(self, tag_id: int, name: str) -> Tag:
        name = name.strip()
        if not name:
            raise ValueError("Tag name must not be empty.")
        return self._tags.rename(tag_id, name)

    def delete_tag(self, tag_id: int) -> None:
        self._tags.delete(tag_id)
