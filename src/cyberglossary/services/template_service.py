"""Template business logic.

Templates are profile-specific and contain an ordered list of section definitions
(title + optional placeholder hint). Applying a template materializes those definitions
into independent ``sections`` rows for a new term; later template changes never affect
previously created terms.
"""

from __future__ import annotations

from cyberglossary.database.models import Template, TemplateSection, Term
from cyberglossary.database.repositories import (
    ProfileNotFoundError,
    ProfileRepository,
    TemplateNotFoundError,
    TemplateRepository,
    TemplateSectionRepository,
)


class TemplateService:
    def __init__(
        self,
        profiles: ProfileRepository,
        templates: TemplateRepository,
        template_sections: TemplateSectionRepository,
    ) -> None:
        self._profiles = profiles
        self._templates = templates
        self._template_sections = template_sections

    # --- templates --------------------------------------------------------

    def create_template(
        self, profile_id: int, name: str, description: str = ""
    ) -> Template:
        name = name.strip()
        if not name:
            raise ValueError("Template name must not be empty.")
        if self._profiles.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        return self._templates.create(profile_id, name, description)

    def get_template(self, template_id: int) -> Template | None:
        return self._templates.get(template_id)

    def list_templates(self, profile_id: int) -> list[Template]:
        return self._templates.list_for_profile(profile_id)

    def rename_template(self, template_id: int, name: str) -> Template:
        name = name.strip()
        if not name:
            raise ValueError("Template name must not be empty.")
        return self._templates.rename(template_id, name)

    def set_description(self, template_id: int, description: str) -> Template:
        return self._templates.set_description(template_id, description)

    def reorder_templates(self, profile_id: int, ordered_ids: list[int]) -> None:
        self._templates.reorder(profile_id, ordered_ids)

    def delete_template(self, template_id: int) -> None:
        self._templates.delete(template_id)

    def duplicate_template(self, template_id: int, new_name: str | None = None) -> Template:
        if new_name is not None:
            new_name = new_name.strip()
            if not new_name:
                raise ValueError("Template name must not be empty.")
        return self._templates.duplicate(template_id, new_name)

    # --- template sections ------------------------------------------------

    def add_section(self, template_id: int, title: str, placeholder: str = "") -> TemplateSection:
        title = title.strip()
        if not title:
            raise ValueError("Template section title must not be empty.")
        if self._templates.get(template_id) is None:
            raise TemplateNotFoundError(template_id)
        return self._template_sections.add(template_id, title, placeholder)

    def list_sections(self, template_id: int) -> list[TemplateSection]:
        return self._template_sections.list_for_template(template_id)

    def set_section_title(self, section_id: int, title: str) -> TemplateSection:
        title = title.strip()
        if not title:
            raise ValueError("Template section title must not be empty.")
        return self._template_sections.set_title(section_id, title)

    def set_section_placeholder(self, section_id: int, placeholder: str) -> TemplateSection:
        return self._template_sections.set_placeholder(section_id, placeholder)

    def reorder_sections(self, template_id: int, ordered_ids: list[int]) -> None:
        self._template_sections.reorder(template_id, ordered_ids)

    def delete_section(self, section_id: int) -> None:
        self._template_sections.delete(section_id)

    # --- apply template ---------------------------------------------------

    def create_term_from_template(
        self, template_id: int, term: str, full_name: str = ""
    ) -> Term:
        term = term.strip()
        if not term:
            raise ValueError("Term name must not be empty.")
        return self._templates.apply(template_id, term, full_name)
