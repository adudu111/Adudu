"""Shared read-only profile data gathering used by JSON and Markdown exporters."""

from __future__ import annotations

from cyberglossary.database.repositories import ProfileNotFoundError


def gather_profile(profile_id: int, profile_service, glossary_service, template_service) -> dict:
    """Collect every piece of a profile's data for serialization.

    Returns a dict with: profile, categories, tags, templates, template_sections
    (id -> list), terms, and term_data (term id -> category/tags/aliases/sections).
    """
    profile = profile_service.get_profile(profile_id)
    if profile is None:
        raise ProfileNotFoundError(profile_id)

    categories = glossary_service.list_categories(profile_id)
    tags = glossary_service.list_tags(profile_id)
    templates = template_service.list_templates(profile_id)
    template_sections = {t.id: template_service.list_sections(t.id) for t in templates}

    terms = glossary_service.list_terms(profile_id)
    term_data = {}
    for term in terms:
        term_data[term.id] = {
            "category": glossary_service.get_term_category(term.id),
            "tags": glossary_service.get_term_tags(term.id),
            "aliases": glossary_service.list_aliases(term.id),
            "sections": glossary_service.list_sections(term.id),
        }

    return {
        "profile": profile,
        "categories": categories,
        "tags": tags,
        "templates": templates,
        "template_sections": template_sections,
        "terms": terms,
        "term_data": term_data,
    }
