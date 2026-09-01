"""Profile export to a deterministic, human-readable JSON document."""

from __future__ import annotations

import json

from cyberglossary import __version__
from cyberglossary.database.models import utcnow
from cyberglossary.import_export._common import gather_profile

SCHEMA_VERSION = 1


def export_profile_dict(
    profile_id: int,
    profile_service,
    glossary_service,
    template_service,
    app_version: str | None = None,
    exported_at: str | None = None,
) -> dict:
    data = gather_profile(profile_id, profile_service, glossary_service, template_service)
    profile = data["profile"]
    term_data = data["term_data"]

    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": app_version or __version__,
        "exported_at": exported_at or utcnow(),
        "profile": {
            "name": profile.name,
            "description": profile.description,
            "color": profile.color,
        },
        "categories": [{"id": c.id, "name": c.name} for c in data["categories"]],
        "tags": [{"id": t.id, "name": t.name} for t in data["tags"]],
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "sections": [
                    {"title": s.title, "placeholder": s.placeholder, "sort_order": s.sort_order}
                    for s in data["template_sections"].get(t.id, [])
                ],
            }
            for t in data["templates"]
        ],
        "terms": [
            {
                "id": term.id,
                "term": term.term,
                "full_name": term.full_name,
                "category_id": td["category"].id if td["category"] else None,
                "tag_ids": [tag.id for tag in td["tags"]],
                "aliases": [a.alias for a in td["aliases"]],
                "sections": [
                    {"title": s.title, "content": s.content, "sort_order": s.sort_order}
                    for s in td["sections"]
                ],
            }
            for term, td in ((term, term_data[term.id]) for term in data["terms"])
        ],
    }


def export_profile_json(profile_id, profile_service, glossary_service, template_service) -> str:
    data = export_profile_dict(
        profile_id, profile_service, glossary_service, template_service
    )
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
