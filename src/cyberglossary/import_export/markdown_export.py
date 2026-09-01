"""Profile export to Markdown (one file per term), with Windows-safe filenames."""

from __future__ import annotations

from cyberglossary.import_export._common import gather_profile

_INVALID_CHARS = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
    f"LPT{i}" for i in range(1, 10)
}
_MAX_NAME_LENGTH = 120


def sanitize_filename(name: str) -> str:
    """Return a Windows-safe filename stem (no extension), without altering the term name."""
    clean = "".join("_" if ch in _INVALID_CHARS or ord(ch) < 32 else ch for ch in name)
    clean = clean.rstrip(" .")
    if clean.upper() in _RESERVED:
        clean = "_" + clean
    if not clean:
        clean = "term"
    if len(clean) > _MAX_NAME_LENGTH:
        clean = clean[:_MAX_NAME_LENGTH]
    return clean


def _dedup(filename: str, used: set[str]) -> str:
    if filename.lower() not in used:
        used.add(filename.lower())
        return filename
    stem = filename.removesuffix(".md")
    counter = 2
    while True:
        candidate = f"{stem} ({counter}).md"
        if candidate.lower() not in used:
            used.add(candidate.lower())
            return candidate
        counter += 1


def term_to_markdown(term: str, full_name: str, category, tags, aliases, sections) -> str:
    lines = [f"# {term}"]
    if full_name:
        lines.append("")
        lines.append(full_name)

    meta = []
    if category:
        meta.append(f"Category: {category}")
    if tags:
        meta.append("Tags: " + ", ".join(tags))
    if aliases:
        meta.append("Aliases: " + ", ".join(aliases))
    if meta:
        lines.append("")
        lines.extend(f"- {item}" for item in meta)

    for section in sections:
        lines.append("")
        lines.append(f"## {section.title}")
        lines.append("")
        if section.content:
            lines.append(section.content)

    return "\n".join(lines) + "\n"


def export_profile_markdown(
    profile_id: int, profile_service, glossary_service, template_service
) -> list[tuple[str, str]]:
    """Return a list of (filename, content) pairs, one Markdown file per term."""
    data = gather_profile(profile_id, profile_service, glossary_service, template_service)
    used: set[str] = set()
    files: list[tuple[str, str]] = []
    for term in data["terms"]:
        td = data["term_data"][term.id]
        content = term_to_markdown(
            term.term,
            term.full_name,
            td["category"].name if td["category"] else None,
            [tag.name for tag in td["tags"]],
            [alias.alias for alias in td["aliases"]],
            td["sections"],
        )
        filename = _dedup(sanitize_filename(term.term) + ".md", used)
        files.append((filename, content))
    return files
