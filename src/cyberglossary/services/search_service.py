"""Local full-text search backed by the SQLite FTS5 index.

The search box (and later the lookup popup) goes through ``SearchService``, which uses a
``SearchQueryBuilder`` to produce a safe FTS5 ``MATCH`` query and a ``SearchRepository`` to
execute it. No network, no external engine.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from cyberglossary.database.repositories import SearchRepository

_MAX_QUERY_LENGTH = 1024
_OPERATORS = {"OR", "AND"}


@dataclass(frozen=True)
class SearchResult:
    term_id: int
    term: str
    full_name: str
    profile_id: int
    profile_name: str
    category: str | None
    snippet: str | None


class SearchQueryBuilder:
    """Builds a safe FTS5 query from arbitrary user input.

    Features: bare tokens, ``"quoted phrases"``, ``token*`` prefix, boolean ``OR``/``AND``,
    and ``-token`` negation. FTS5 only supports binary ``NOT`` natively, so negation is
    handled by ``negated_terms()`` (excluded at the service layer). Everything else is
    sanitized so malformed input can never reach FTS5 as a syntax error.
    """

    @classmethod
    def build(cls, query: str) -> str:
        """Return the positive FTS5 MATCH string (negated terms excluded)."""
        positive, _ = cls._parse(query)
        return " ".join(positive)

    @classmethod
    def negated_terms(cls, query: str) -> list[str]:
        """Return the sanitized negated terms (e.g. ``-tgt`` → ``["tgt"]``)."""
        _, negated = cls._parse(query)
        return negated

    @classmethod
    def _parse(cls, query: str) -> tuple[list[str], list[str]]:
        if not query:
            return [], []
        query = query[:_MAX_QUERY_LENGTH]
        positive: list[str] = []
        negated: list[str] = []
        for token in cls._tokenize(query):
            if len(token) >= 2 and token.startswith('"') and token.endswith('"'):
                positive.append(token)
                continue
            if token.upper() in _OPERATORS:
                positive.append(token.upper())
                continue
            is_negated = token.startswith("-") and len(token) > 1
            if is_negated:
                token = token[1:]
            prefix = token.endswith("*") and len(token) > 1
            if prefix:
                token = token[:-1]
            core = cls._sanitize(token)
            if not core:
                continue
            if prefix:
                core += "*"
            if is_negated:
                negated.append(core)
            else:
                positive.append(core)
        return positive, negated

    @classmethod
    def _tokenize(cls, query: str) -> list[str]:
        tokens: list[str] = []
        i = 0
        n = len(query)
        while i < n:
            ch = query[i]
            if ch.isspace():
                i += 1
                continue
            if ch == '"':
                j = i + 1
                buf: list[str] = []
                while j < n and query[j] != '"':
                    buf.append(query[j])
                    j += 1
                phrase = "".join(buf).strip()
                if phrase:
                    tokens.append('"' + phrase.replace('"', "") + '"')
                i = j + 1
                continue
            j = i
            while j < n and not query[j].isspace():
                j += 1
            tokens.append(query[i:j])
            i = j
        return tokens

    @staticmethod
    def _sanitize(token: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "", token)


class SearchService:
    def __init__(self, repository: SearchRepository) -> None:
        self._repository = repository

    def search(self, query: str, profile_id: int | None = None) -> list[SearchResult]:
        """Search within a profile (``profile_id``) or across all profiles (``None``)."""
        positive = SearchQueryBuilder.build(query)
        negated = SearchQueryBuilder.negated_terms(query)
        if not positive and not negated:
            return []

        exclude: set[int] = set()
        for term in negated:
            exclude |= self._rowids(term, profile_id)

        try:
            if positive:
                rows = self._repository.search(positive, profile_id)
            else:
                rows = self._repository.fetch_terms(profile_id)
        except sqlite3.OperationalError:
            # Malformed FTS5 input must fail safely, never crash the app.
            return []

        return [
            self._to_result(row)
            for row in rows
            if row["term_id"] not in exclude
        ]

    def _rowids(self, term: str, profile_id: int | None) -> set[int]:
        try:
            return self._repository.search_rowids(term, profile_id)
        except sqlite3.OperationalError:
            return set()

    @staticmethod
    def _to_result(row) -> SearchResult:
        snippet = row["snippet"]
        if snippet:
            snippet = snippet.replace("[[", "").replace("]]", "")
        return SearchResult(
            term_id=row["term_id"],
            term=row["term"],
            full_name=row["full_name"],
            profile_id=row["profile_id"],
            profile_name=row["profile_name"],
            category=row["category"] or None,
            snippet=snippet or None,
        )
