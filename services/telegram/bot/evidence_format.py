"""Format tool payloads as readable evidence blocks for the Librarian model."""

from __future__ import annotations

from typing import Any

_SECTION_ORDER = ("expanded", "notes", "post")


def _strip_frontmatter(text: str) -> str:
    from markdown_io import split_markdown_parts

    _, body = split_markdown_parts(text)
    return body.strip()


def format_load_episode_for_tool(payload: dict[str, Any]) -> str:
    """Readable episode load block aligned with search evidence shape."""
    episode_id = str(payload.get("episode_id") or "")
    meta = payload.get("meta") or {}
    title = str(meta.get("title") or episode_id)
    listened = meta.get("listened")
    listened_label = "true" if listened else "false" if listened is not None else "unknown"

    lines = [
        f"### Episode {episode_id} — {title}",
        f"Listened: {listened_label}",
        "",
        "Loaded episode (cite only from this block; use [ep-NNNN]):",
        "",
    ]

    sections = payload.get("sections") or {}
    wrote_section = False
    for key in _SECTION_ORDER:
        raw = sections.get(key)
        if not raw:
            continue
        body = _strip_frontmatter(str(raw))
        if not body:
            continue
        lines.append(f"#### {key}")
        lines.append("")
        lines.append(body)
        lines.append("")
        wrote_section = True

    if not wrote_section:
        lines.append("No on-disk sections available for this episode.")

    return "\n".join(lines).strip()
