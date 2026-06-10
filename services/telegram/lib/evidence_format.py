"""Format tool payloads as readable evidence blocks for the Librarian model."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CITE_FOOTER = "cite only from this block; use [ep-NNNN]"

_SECTION_ORDER = ("expanded", "notes", "post")


def _strip_frontmatter(text: str) -> str:
    from markdown_io import split_markdown_parts

    _, body = split_markdown_parts(text)
    return body.strip()


def format_evidence_for_tool(
    bundle,
    *,
    label: str | None = None,
    max_chunks: int = 8,
) -> str:
    """Readable evidence block returned from search_vault / search_vault_many."""
    chunk_dicts = [
        {
            "chunk_id": ch.chunk_id,
            "episode_id": ch.episode_id,
            "title": ch.title,
            "section": ch.section,
            "excerpt": ch.excerpt,
            "rerank_score": ch.rerank_score,
        }
        for ch in bundle.chunks
    ]
    return format_search_evidence(chunk_dicts, label=label, max_chunks=max_chunks)


def format_search_evidence(
    chunks: Sequence[Mapping[str, Any]],
    *,
    label: str | None = None,
    max_chunks: int = 8,
    empty_message: str = "No citable evidence found for this query.",
) -> str:
    """Readable evidence block for search_vault / search_vault_many."""
    if not chunks:
        header = f"### {label}\n" if label else ""
        return f"{header}{empty_message}"

    lines: list[str] = []
    if label:
        lines.append(f"### {label}")
        lines.append("")
    lines.append(f"Retrieved evidence ({CITE_FOOTER}):")
    lines.append("")
    for i, ch in enumerate(chunks[:max_chunks], start=1):
        chunk_id = str(ch.get("chunk_id", ""))
        episode_id = str(ch.get("episode_id", ""))
        title = str(ch.get("title", ""))
        section = str(ch.get("section", ""))
        excerpt = str(ch.get("excerpt", ""))
        score = float(ch.get("rerank_score") or 0.0)
        lines.append(
            f"#### Evidence {i} — {chunk_id} [{episode_id}]\n"
            f"Title: {title}\nSection: {section}\n"
            f"Score: {score:.1f}\n\n{excerpt}\n"
        )
    return "\n".join(lines)


def format_transcript_evidence(
    hits: Sequence[Mapping[str, Any]],
    *,
    empty_message: str = "No transcript hits for this query.",
) -> str:
    """Readable evidence block for search_transcript."""
    if not hits:
        return empty_message

    lines = [
        f"Transcript hits ({CITE_FOOTER}):",
        "",
    ]
    for i, hit in enumerate(hits, start=1):
        episode_id = str(hit.get("episode_id", ""))
        lines.append(
            f"#### Hit {i} — {hit.get('chunk_id', '')} [{episode_id}]\n"
            f"Section: {hit.get('section', '')}\n\n{hit.get('excerpt', '')}\n"
        )
    return "\n".join(lines)


def trace_evidence_from_hits(
    hits: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compact chunk metadata for tool_trace."""
    return [
        {
            "chunk_id": hit.get("chunk_id", ""),
            "episode_id": hit.get("episode_id", ""),
            "section": hit.get("section", ""),
        }
        for hit in hits
    ]


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
        f"Loaded episode ({CITE_FOOTER}):",
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
