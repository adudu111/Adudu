"""Lookup pipeline: capture selected text, normalize, and resolve a term.

Resolution is deterministic and offline: exact term (case-insensitive) → exact alias
(case-insensitive) → FTS best match → not found, scoped to the active profile. The result
is a ``LookupResult`` that the UI (popup) renders; no text is logged or persisted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from cyberglossary.database.models import Section
from cyberglossary.services.glossary_service import GlossaryService
from cyberglossary.services.profile_service import ProfileService
from cyberglossary.services.search_service import SearchService


def normalize_selected_text(text: str) -> str:
    """Deterministically normalize captured text.

    - trim leading/trailing whitespace
    - collapse internal line breaks/whitespace to single spaces
    - strip surrounding quotes
    - extract the leading candidate before a parenthesized full name
    - strip trailing punctuation
    """
    if not text:
        return ""
    collapsed = " ".join(text.split())
    if len(collapsed) >= 2 and collapsed[0] == collapsed[-1] and collapsed[0] in "\"'":
        collapsed = collapsed[1:-1].strip()
    paren = collapsed.find("(")
    if paren > 0:
        collapsed = collapsed[:paren].strip()
    return collapsed.rstrip(".,;:!?\u2026").strip()


@dataclass(frozen=True)
class LookupResult:
    found: bool
    query: str | None
    term_id: int | None
    term: str | None
    full_name: str | None
    category: str | None
    tags: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    profile_name: str | None = None

    @staticmethod
    def not_found(query: str | None = None) -> LookupResult:
        return LookupResult(False, query, None, None, None, None, [], [], None)


class LookupService:
    def __init__(
        self,
        capture_text: Callable[[], str | None],
        profiles: ProfileService,
        glossary: GlossaryService,
        search: SearchService,
    ) -> None:
        self._capture_text = capture_text
        self._profiles = profiles
        self._glossary = glossary
        self._search = search

    def capture_and_normalize(self) -> str | None:
        text = self._capture_text()
        if not text:
            return None
        normalized = normalize_selected_text(text)
        return normalized or None

    def run(self) -> LookupResult:
        text = self.capture_and_normalize()
        if not text:
            return LookupResult.not_found(None)
        return self.lookup(text)

    def lookup(self, text: str) -> LookupResult:
        normalized = normalize_selected_text(text)
        if not normalized:
            return LookupResult.not_found(text)

        profile_id = self._profiles.get_active_profile_id()
        if profile_id is None:
            return LookupResult.not_found(normalized)

        # Exact term, then exact alias, then FTS fallback.
        term = self._glossary.get_term_by_name(profile_id, normalized)
        if term is None:
            term = self._glossary.find_term_by_alias(profile_id, normalized)
        if term is None:
            results = self._search.search(normalized, profile_id)
            if results:
                term = self._glossary.get_term(results[0].term_id)
        if term is None:
            return LookupResult.not_found(normalized)

        return self._to_result(term)

    def _to_result(self, term) -> LookupResult:
        profile = self._profiles.get_profile(term.profile_id)
        category = self._glossary.get_term_category(term.id)
        tags = self._glossary.get_term_tags(term.id)
        sections = self._glossary.list_sections(term.id)
        return LookupResult(
            found=True,
            query=term.term,
            term_id=term.id,
            term=term.term,
            full_name=term.full_name or None,
            category=category.name if category else None,
            tags=[tag.name for tag in tags],
            sections=sections,
            profile_name=profile.name if profile else None,
        )
