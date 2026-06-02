"""Markdown frontmatter read/write and notes datapoint detection."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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

# Canonical content_type values stored in frontmatter
CONTENT_TYPE_TRANSCRIPT = "transcript"
CONTENT_TYPE_NOTES = "notes"
CONTENT_TYPE_POST = "post"
CONTENT_TYPE_EXPANDED = "expanded"
CONTENT_TYPE_EXPANDED_DRAFT = "expanded.draft"

CORE_FRONTMATTER_KEYS = (
    "id",
    "episode_number",
    "title",
    "content_type",
    "source",
    "published_at",
    "founders_url",
    "created_at",
)

TYPE_SPECIFIC_KEYS: dict[str, tuple[str, ...]] = {
    CONTENT_TYPE_TRANSCRIPT: ("colossus_url", "fetched_at"),
    CONTENT_TYPE_NOTES: ("imported_at",),
    CONTENT_TYPE_POST: (
        "x_url",
        "x_post_id",
        "imported_at",
        "post_kind",
        "attribution_note",
        "alt_source",
    ),
    CONTENT_TYPE_EXPANDED_DRAFT: (
        "model",
        "generated_at",
        "prompt_path",
        "prompt_hash",
        "tune_variant",
    ),
    CONTENT_TYPE_EXPANDED: ("expanded_at", "expanded_model", "prompt_hash"),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


TIMESTAMP_BULLET_RE = re.compile(
    r"^[\s]*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*.+$",
    re.MULTILINE,
)

# Bullets with em dash but no MM:SS (timestamp lost or never added).
LOST_TIMESTAMP_BULLET_RE = re.compile(
    r"^[\s]*-\s*[-–—]\s*.*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class NotesDatapointCounts:
    timestamped: int
    missing_timestamp: int


def count_notes_datapoints(body: str) -> NotesDatapointCounts:
    """Count timestamped vs `- — …` bullets in a notes body."""
    return NotesDatapointCounts(
        timestamped=len(TIMESTAMP_BULLET_RE.findall(body)),
        missing_timestamp=len(LOST_TIMESTAMP_BULLET_RE.findall(body)),
    )


def count_notes_datapoints_file(path: Path) -> NotesDatapointCounts:
    return count_notes_datapoints(read_markdown_body(path))


def escape_yaml_value(value: str) -> str:
    return value.replace('"', "'")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Best-effort key: value from first YAML frontmatter block."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def split_markdown_parts(text: str) -> tuple[dict[str, str] | None, str]:
    """
    Split file into (frontmatter dict or None, body).
    Body is returned exactly as stored after the closing --- (not stripped).
    """
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parse_frontmatter(text), parts[2]


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_markdown_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    _, body = split_markdown_parts(text)
    return body.strip()


def has_timestamp_datapoints(path: Path) -> bool:
    return count_notes_datapoints_file(path).timestamped > 0


def episode_frontmatter(
    row: dict[str, Any],
    *,
    content_type: str,
    source: str,
    created_at: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build canonical ordered frontmatter for an episode markdown file."""
    if content_type not in {
        CONTENT_TYPE_TRANSCRIPT,
        CONTENT_TYPE_NOTES,
        CONTENT_TYPE_POST,
        CONTENT_TYPE_EXPANDED,
        CONTENT_TYPE_EXPANDED_DRAFT,
    }:
        raise ValueError(f"unknown content_type: {content_type}")

    fm: dict[str, Any] = {
        "id": row["id"],
        "title": row["title"],
        "content_type": content_type,
        "source": source,
        "created_at": created_at,
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    if row.get("published_at"):
        fm["published_at"] = row["published_at"]
    if row.get("founders_url"):
        fm["founders_url"] = row["founders_url"]
    if extra:
        for key, val in extra.items():
            if val is not None and val != "":
                fm[key] = val
    return fm


def ordered_frontmatter(fm: dict[str, Any]) -> dict[str, Any]:
    """Reorder keys: core fields first, then type-specific, then any remainder."""
    ordered: dict[str, Any] = {}
    for key in CORE_FRONTMATTER_KEYS:
        if key in fm and fm[key] is not None:
            ordered[key] = fm[key]
    ctype = str(fm.get("content_type", ""))
    for key in TYPE_SPECIFIC_KEYS.get(ctype, ()):
        if key in fm and fm[key] is not None:
            ordered[key] = fm[key]
    for key, val in fm.items():
        if key not in ordered and val is not None:
            ordered[key] = val
    return ordered


def serialize_frontmatter(fm: dict[str, Any]) -> str:
    lines = ["---"]
    for key, val in ordered_frontmatter(fm).items():
        if val is None:
            continue
        if isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, int):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f'{key}: "{escape_yaml_value(str(val))}"')
    lines.append("---")
    return "\n".join(lines)


def write_frontmatter_md(
    path: Path,
    *,
    frontmatter: dict[str, Any],
    body: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = serialize_frontmatter(frontmatter) + "\n\n" + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def rewrite_frontmatter_preserving_body(
    path: Path,
    *,
    frontmatter: dict[str, Any],
) -> tuple[Path, str]:
    """
    Rewrite only the frontmatter block; body bytes after closing --- unchanged.
    Returns (path, body_hash_before).
    """
    text = path.read_text(encoding="utf-8")
    old_fm, body = split_markdown_parts(text)
    if old_fm is None:
        before_hash = body_hash(text)
        new_text = serialize_frontmatter(frontmatter) + body
    else:
        before_hash = body_hash(body)
        new_text = serialize_frontmatter(frontmatter) + body
    after_fm, after_body = split_markdown_parts(new_text)
    if after_fm is not None and body_hash(after_body) != before_hash:
        raise ValueError(
            f"body changed after frontmatter rewrite: {path}"
        )
    path.write_text(new_text, encoding="utf-8")
    return path, before_hash


def infer_content_type_from_filename(name: str) -> str | None:
    if name.endswith(".transcript.md"):
        return CONTENT_TYPE_TRANSCRIPT
    if name.endswith(".notes.md"):
        return CONTENT_TYPE_NOTES
    if name.endswith(".post.md"):
        return CONTENT_TYPE_POST
    if name.endswith(".expanded.draft.md"):
        return CONTENT_TYPE_EXPANDED_DRAFT
    if name.endswith(".expanded.md"):
        return CONTENT_TYPE_EXPANDED
    return None


def normalize_frontmatter_from_existing(
    row: dict[str, Any],
    existing: dict[str, str],
    content_type: str,
) -> dict[str, Any]:
    """Merge catalog row + legacy frontmatter into canonical shape."""
    source = existing.get("source") or "unknown"
    created_at = (
        existing.get("created_at")
        or existing.get("imported_at")
        or existing.get("fetched_at")
        or existing.get("generated_at")
        or existing.get("expanded_at")
        or utc_now_iso()
    )
    published_at = existing.get("published_at") or row.get("published_at")
    if content_type == CONTENT_TYPE_POST and existing.get("published_at"):
        published_at = existing.get("published_at")

    extra: dict[str, Any] = {}
    for key in (
        "fetched_at",
        "imported_at",
        "colossus_url",
        "x_url",
        "x_post_id",
        "post_kind",
        "attribution_note",
        "alt_source",
        "model",
        "generated_at",
        "prompt_path",
        "prompt_hash",
        "tune_variant",
        "expanded_at",
        "expanded_model",
    ):
        if key in existing and existing[key]:
            extra[key] = existing[key]

    if content_type == CONTENT_TYPE_TRANSCRIPT:
        if "fetched_at" in existing:
            extra["fetched_at"] = existing["fetched_at"]
        if row.get("colossus_url"):
            extra["colossus_url"] = row.get("colossus_url") or existing.get(
                "colossus_url", ""
            )
        elif existing.get("colossus_url"):
            extra["colossus_url"] = existing["colossus_url"]

    if content_type == CONTENT_TYPE_NOTES and existing.get("imported_at"):
        extra["imported_at"] = existing["imported_at"]

    if content_type == CONTENT_TYPE_POST:
        for key in (
            "x_url",
            "x_post_id",
            "imported_at",
            "post_kind",
            "attribution_note",
            "alt_source",
        ):
            if existing.get(key):
                extra[key] = existing[key]

    if content_type == CONTENT_TYPE_EXPANDED_DRAFT:
        for key in (
            "model",
            "generated_at",
            "prompt_path",
            "prompt_hash",
            "tune_variant",
        ):
            if existing.get(key):
                extra[key] = existing[key]

    if content_type == CONTENT_TYPE_EXPANDED:
        if existing.get("expanded_at"):
            extra["expanded_at"] = existing["expanded_at"]
        if existing.get("expanded_model"):
            extra["expanded_model"] = existing["expanded_model"]
        elif existing.get("model"):
            extra["expanded_model"] = existing["model"]
        if existing.get("prompt_hash"):
            extra["prompt_hash"] = existing["prompt_hash"]

    fm = episode_frontmatter(
        {**row, "published_at": published_at},
        content_type=content_type,
        source=source,
        created_at=created_at,
        extra=extra,
    )
    return fm


def validate_frontmatter(
    path: Path,
    fm: dict[str, str],
    *,
    expected_id: str | None = None,
) -> list[str]:
    """Return human-readable validation errors for a frontmatter dict."""
    errors: list[str] = []
    rel = str(path)
    for key in (
        "id",
        "title",
        "content_type",
        "source",
        "published_at",
        "founders_url",
        "created_at",
    ):
        if not fm.get(key):
            errors.append(f"{rel}: missing frontmatter {key}")
    if expected_id and expected_id.startswith("ep-") and not expected_id.startswith("ep-special-"):
        if not fm.get("episode_number"):
            errors.append(f"{rel}: missing frontmatter episode_number")
    ctype = fm.get("content_type", "")
    if ctype and ctype not in {
        CONTENT_TYPE_TRANSCRIPT,
        CONTENT_TYPE_NOTES,
        CONTENT_TYPE_POST,
        CONTENT_TYPE_EXPANDED,
        CONTENT_TYPE_EXPANDED_DRAFT,
    }:
        errors.append(f"{rel}: invalid content_type {ctype!r}")
    if expected_id and fm.get("id") and fm.get("id") != expected_id:
        errors.append(f"{rel}: id {fm.get('id')!r} != expected {expected_id!r}")
    inferred = infer_content_type_from_filename(path.name)
    if inferred and fm.get("content_type") and fm.get("content_type") != inferred:
        errors.append(
            f"{rel}: content_type {fm.get('content_type')!r} != filename {inferred!r}"
        )
    for key in TYPE_SPECIFIC_KEYS.get(ctype, ()):
        if key in (
            "post_kind",
            "attribution_note",
            "alt_source",
            "tune_variant",
            "prompt_hash",
            "expanded_model",
        ):
            continue
        if not fm.get(key):
            errors.append(f"{rel}: missing type-specific {key}")
    return errors


def write_notes_md(row: dict[str, Any], body: str, *, source: str = "vault_native") -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    path = notes_file_path(episode_id, slug, num)
    now = utc_now_iso()
    fm = episode_frontmatter(
        row,
        content_type=CONTENT_TYPE_NOTES,
        source=source,
        created_at=now,
        extra={"imported_at": now},
    )
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
    now = utc_now_iso()
    extra: dict[str, Any] = {
        "x_url": x_url,
        "x_post_id": x_post_id,
        "imported_at": now,
    }
    if post_kind:
        extra["post_kind"] = post_kind
    if alt_source:
        extra["alt_source"] = alt_source
    if attribution_note:
        extra["attribution_note"] = attribution_note
    if extra_fm:
        extra.update(extra_fm)
    row_pub = {**row}
    if published_at:
        row_pub["published_at"] = published_at
    fm = episode_frontmatter(
        row_pub,
        content_type=CONTENT_TYPE_POST,
        source=source,
        created_at=now,
        extra=extra,
    )
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_transcript_md(row: dict[str, Any], body: str, fetched_at: str) -> Path:
    episode_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    out_dir = transcript_dir(episode_id, slug, num)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / transcript_filename(episode_id, slug, num)
    extra = {
        "colossus_url": row.get("colossus_url") or "",
        "fetched_at": fetched_at,
    }
    fm = episode_frontmatter(
        row,
        content_type=CONTENT_TYPE_TRANSCRIPT,
        source="colossus",
        created_at=fetched_at,
        extra=extra,
    )
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_expanded_draft_md(
    row: dict[str, Any],
    *,
    model: str,
    prompt_path: str,
    prompt_hash: str,
    generated_at: str | None = None,
    tune_variant: str | None = None,
) -> dict[str, Any]:
    """Return frontmatter dict for expanded draft (caller writes file)."""
    gen = generated_at or utc_now_iso()
    extra: dict[str, Any] = {
        "model": model,
        "generated_at": gen,
        "prompt_path": prompt_path,
        "prompt_hash": prompt_hash,
    }
    if tune_variant:
        extra["tune_variant"] = tune_variant
    return episode_frontmatter(
        row,
        content_type=CONTENT_TYPE_EXPANDED_DRAFT,
        source="expand_llm",
        created_at=gen,
        extra=extra,
    )


def write_expanded_md(
    row: dict[str, Any],
    body: str,
    *,
    expanded_at: str | None = None,
    expanded_model: str | None = None,
    prompt_hash: str | None = None,
) -> Path:
    from paths import expanded_file_path

    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    path = expanded_file_path(ep_id, slug, num)
    at = expanded_at or utc_now_iso()
    extra: dict[str, Any] = {"expanded_at": at}
    if expanded_model:
        extra["expanded_model"] = expanded_model
    if prompt_hash:
        extra["prompt_hash"] = prompt_hash
    fm = episode_frontmatter(
        row,
        content_type=CONTENT_TYPE_EXPANDED,
        source="expand_llm",
        created_at=at,
        extra=extra,
    )
    return write_frontmatter_md(path, frontmatter=fm, body=body)
