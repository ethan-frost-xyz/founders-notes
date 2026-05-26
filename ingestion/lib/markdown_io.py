"""Markdown frontmatter read/write and notes datapoint detection."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import (
    _episode_folder,
    notes_file_path,
    post_file_path,
    transcript_dir,
    transcript_filename,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


TIMESTAMP_BULLET_RE = re.compile(
    r"^[\s]*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*.+$",
    re.MULTILINE,
)


def read_markdown_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        return (parts[2] if len(parts) >= 3 else text).strip()
    return text.strip()


def has_timestamp_datapoints(path: Path) -> bool:
    return bool(TIMESTAMP_BULLET_RE.search(read_markdown_body(path)))


def escape_yaml_value(value: str) -> str:
    return value.replace('"', "'")


def write_frontmatter_md(
    path: Path,
    *,
    frontmatter: dict[str, Any],
    body: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, val in frontmatter.items():
        if val is None:
            continue
        if isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, int):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f'{key}: "{escape_yaml_value(str(val))}"')
    lines.extend(["---", "", body.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_notes_md(row: dict[str, Any], body: str, *, source: str = "vault_native") -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    path = notes_file_path(episode_id, slug, num)
    fm: dict[str, Any] = {
        "id": episode_id,
        "title": row["title"],
        "source": source,
        "imported_at": utc_now_iso(),
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_post_md(
    row: dict[str, Any],
    body: str,
    *,
    x_url: str,
    x_post_id: str,
    published_at: str | None = None,
    source: str = "x_api",
    post_kind: str | None = None,
    alt_source: str | None = None,
    attribution_note: str | None = None,
    extra_fm: dict[str, Any] | None = None,
) -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    path = post_file_path(episode_id, slug, num)
    fm: dict[str, Any] = {
        "id": episode_id,
        "title": row["title"],
        "x_url": x_url,
        "x_post_id": x_post_id,
        "source": source,
        "imported_at": utc_now_iso(),
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    if published_at:
        fm["published_at"] = published_at
    if post_kind:
        fm["post_kind"] = post_kind
    if alt_source:
        fm["alt_source"] = alt_source
    if attribution_note:
        fm["attribution_note"] = attribution_note
    if extra_fm:
        fm.update(extra_fm)
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_transcript_md(row: dict[str, Any], body: str, fetched_at: str) -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    out_dir = transcript_dir(episode_id, slug, num)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / transcript_filename(episode_id, slug, num)
    for legacy_name in ("transcript.md", f"{_episode_folder(episode_id, slug, num)}.md"):
        legacy = out_dir / legacy_name
        if legacy.exists() and legacy != path:
            legacy.unlink()
    fm: dict[str, Any] = {
        "id": episode_id,
        "title": row["title"],
        "published_at": row.get("published_at") or "unknown",
        "colossus_url": row.get("colossus_url") or "",
        "founders_url": row["founders_url"],
        "source": "colossus",
        "fetched_at": fetched_at,
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    return write_frontmatter_md(path, frontmatter=fm, body=body)
