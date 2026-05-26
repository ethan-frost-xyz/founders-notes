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
from markdown_io import parse_frontmatter, read_markdown_body, utc_now_iso
from paths import (
    CHUNKS_PATH,
    ROOT,
    expanded_file_path,
    notes_file_path,
    post_file_path,
    transcript_dir,
    transcript_filename,
)

SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
CHUNK_LINES = 80
CHUNK_CHARS = 4000


def split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return [("body", text.strip())]
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower().replace(" ", "_")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((name, body))
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
        chunk_id = f"{episode_id}#{section}#{start_line}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "id": episode_id,
                "section": section,
                "start_line": start_line,
                "end_line": end_line,
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


def index_markdown_file(
    path: Path,
    episode_id: str,
    content_type: str,
    row: dict[str, Any],
) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(raw)
    text = read_markdown_body(path)
    rel = str(path.relative_to(ROOT))
    meta = chunk_metadata(row, fm, content_type)
    all_chunks: list[dict[str, Any]] = []
    for section, body in split_sections(text):
        section_key = f"{content_type}:{section}"
        all_chunks.extend(chunk_body(episode_id, section_key, body, rel, meta))
    return all_chunks


def build_all_chunks(rows: list[dict[str, Any]] | None = None) -> int:
    """Scan catalog content and overwrite catalog/chunks.jsonl. Returns chunk count."""
    if rows is None:
        rows = load_catalog()
    all_chunks: list[dict[str, Any]] = []

    for row in rows:
        ep_id = row["id"]
        slug = row["slug"]
        num = row.get("episode_number")

        tx_path = transcript_dir(ep_id, slug, num) / transcript_filename(ep_id, slug, num)
        if tx_path.exists():
            all_chunks.extend(index_markdown_file(tx_path, ep_id, "transcript", row))

        npath = notes_file_path(ep_id, slug, num)
        if npath.exists():
            all_chunks.extend(index_markdown_file(npath, ep_id, "notes", row))

        expanded = expanded_file_path(ep_id, slug, num)
        if expanded.exists():
            all_chunks.extend(index_markdown_file(expanded, ep_id, "expanded", row))

        ppath = post_file_path(ep_id, slug, num)
        if ppath.exists():
            all_chunks.extend(index_markdown_file(ppath, ep_id, "post", row))

    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for ch in all_chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    return len(all_chunks)


def main() -> None:
    n = build_all_chunks()
    print(f"Wrote {n} chunks to {CHUNKS_PATH.relative_to(ROOT)}")
    print(f"built_at: {utc_now_iso()}")


if __name__ == "__main__":
    main()
