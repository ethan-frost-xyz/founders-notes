#!/usr/bin/env python3
"""Build catalog/chunks.jsonl for Retrieval v1 (grep-friendly, embedding-ready)."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import json
import re
from pathlib import Path
from typing import Any

from catalog import load_catalog
from markdown_io import (
    has_timestamp_datapoints,
    parse_frontmatter,
    read_markdown_body,
    split_markdown_parts,
    utc_now_iso,
)
import paths
from paths import (
    expanded_file_path,
    notes_file_path,
    post_file_path,
    transcript_dir,
    transcript_filename,
)

SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
DATAPOINT_HEADING_RE = re.compile(r"^###\s+", re.MULTILINE)
CHUNK_LINES = 80
CHUNK_CHARS = 4000


def body_start_line_in_file(raw: str) -> int:
    """1-based line number of the first line of markdown body after frontmatter."""
    if not raw.startswith("---"):
        return 1
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return 1
    return parts[0].count("\n") + parts[1].count("\n") + 3


def split_sections(text: str) -> list[tuple[str, str, int]]:
    """Split body into (section_name, body, content_start_line) with 1-based lines in text."""
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        body = text.strip()
        if not body:
            return []
        return [("body", body, 1)]
    sections: list[tuple[str, str, int]] = []
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower().replace(" ", "_")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end]
        body = section_text.strip()
        if not body:
            continue
        content_start = start
        while content_start < end and text[content_start] in "\n\r":
            content_start += 1
        content_line = text[:content_start].count("\n") + 1
        sections.append((name, body, content_line))
    return sections


def chunk_metadata(
    row: dict[str, Any],
    fm: dict[str, str],
    content_type: str,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "title": fm.get("title") or row.get("title"),
        "content_type": fm.get("content_type") or content_type,
        "source": fm.get("source"),
    }
    ep_num = fm.get("episode_number") or row.get("episode_number")
    if ep_num is not None:
        try:
            meta["episode_number"] = int(ep_num)
        except (TypeError, ValueError):
            meta["episode_number"] = ep_num
    pub = fm.get("published_at") or row.get("published_at")
    if pub:
        meta["published_at"] = pub
    if fm.get("founders_url") or row.get("founders_url"):
        meta["founders_url"] = fm.get("founders_url") or row.get("founders_url")
    return meta


def chunk_body(
    episode_id: str,
    section: str,
    body: str,
    source_path: str,
    meta: dict[str, Any],
    *,
    line_offset: int = 0,
) -> list[dict[str, Any]]:
    lines = body.splitlines()
    chunks: list[dict[str, Any]] = []
    if not lines:
        return chunks

    start_line = 1
    buf: list[str] = []
    buf_chars = 0

    def flush(end_line: int) -> None:
        nonlocal start_line, buf, buf_chars
        if not buf:
            return
        excerpt = "\n".join(buf).strip()
        abs_start = start_line + line_offset
        abs_end = end_line + line_offset
        chunk_id = f"{episode_id}#{section}#{abs_start}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "id": episode_id,
                "section": section,
                "start_line": abs_start,
                "end_line": abs_end,
                "source_path": source_path,
                "excerpt": excerpt[:2000],
                "char_count": len(excerpt),
                **meta,
            }
        )
        buf.clear()
        buf_chars = 0

    for i, line in enumerate(lines, start=1):
        buf.append(line)
        buf_chars += len(line) + 1
        if len(buf) >= CHUNK_LINES or buf_chars >= CHUNK_CHARS:
            flush(i)
            start_line = i + 1

    if buf:
        flush(start_line + len(buf) - 1)

    return chunks


def chunk_expanded_datapoints(
    episode_id: str,
    section: str,
    body: str,
    source_path: str,
    meta: dict[str, Any],
    *,
    line_offset: int,
) -> list[dict[str, Any]]:
    """One chunk per ### datapoint; fall back to windowed chunking when none."""
    matches = list(DATAPOINT_HEADING_RE.finditer(body))
    if not matches:
        return chunk_body(
            episode_id,
            section,
            body,
            source_path,
            meta,
            line_offset=line_offset,
        )

    chunks: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        dp_body = body[start:end].strip()
        if not dp_body:
            continue
        dp_start_in_body = body[:start].count("\n") + 1
        dp_end_in_body = body[:end].count("\n")
        abs_start = dp_start_in_body + line_offset
        abs_end = dp_end_in_body + line_offset
        chunk_id = f"{episode_id}#{section}#{abs_start}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "id": episode_id,
                "section": section,
                "start_line": abs_start,
                "end_line": abs_end,
                "source_path": source_path,
                "excerpt": dp_body[:2000],
                "char_count": len(dp_body),
                **meta,
            }
        )
    return chunks


def index_markdown_file(
    path: Path,
    episode_id: str,
    content_type: str,
    row: dict[str, Any],
) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(raw)
    _, body_raw = split_markdown_parts(raw)
    text = body_raw.strip()
    rel = str(path.relative_to(paths.ROOT))
    meta = chunk_metadata(row, fm, content_type)
    body_line_base = body_start_line_in_file(raw) - 1
    all_chunks: list[dict[str, Any]] = []
    for section, section_body, section_line in split_sections(text):
        section_key = f"{content_type}:{section}"
        line_offset = body_line_base + section_line - 1
        if content_type == "expanded":
            all_chunks.extend(
                chunk_expanded_datapoints(
                    episode_id,
                    section_key,
                    section_body,
                    rel,
                    meta,
                    line_offset=line_offset,
                )
            )
        else:
            all_chunks.extend(
                chunk_body(
                    episode_id,
                    section_key,
                    section_body,
                    rel,
                    meta,
                    line_offset=line_offset,
                )
            )
    return all_chunks


def episode_is_listened(notes_path: Path) -> bool:
    """True when notes contain at least one timestamp bullet (studied episode)."""
    if not notes_path.is_file():
        return False
    return has_timestamp_datapoints(notes_path)


def build_all_chunks(rows: list[dict[str, Any]] | None = None) -> int:
    """Scan catalog content and overwrite catalog/chunks.jsonl. Returns chunk count."""
    if rows is None:
        rows = load_catalog()
    all_chunks: list[dict[str, Any]] = []

    for row in rows:
        ep_id = row["id"]
        slug = row["slug"]
        num = row.get("episode_number")

        npath = notes_file_path(ep_id, slug, num)
        listened = episode_is_listened(npath)

        tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)
        if tx_path.exists() and listened:
            all_chunks.extend(index_markdown_file(tx_path, ep_id, "transcript", row))

        if npath.exists():
            all_chunks.extend(index_markdown_file(npath, ep_id, "notes", row))

        expanded = expanded_file_path(ep_id, slug, num)
        if expanded.exists():
            all_chunks.extend(index_markdown_file(expanded, ep_id, "expanded", row))

        ppath = post_file_path(ep_id, slug, num)
        if ppath.exists():
            all_chunks.extend(index_markdown_file(ppath, ep_id, "post", row))

    out = paths.CHUNKS_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    return len(all_chunks)


def main() -> None:
    n = build_all_chunks()
    print(f"Wrote {n} chunks to {paths.CHUNKS_PATH.relative_to(paths.ROOT)}")
    print(f"built_at: {utc_now_iso()}")


if __name__ == "__main__":
    main()
