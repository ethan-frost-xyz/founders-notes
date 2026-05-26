"""Filesystem layout and catalog id consistency checks."""

from __future__ import annotations

import re

from episode_ids import EPISODE_NUMBER_WIDTH, format_episode_id
from markdown_io import infer_content_type_from_filename, parse_frontmatter, validate_frontmatter
from paths import CONTENT_TYPES, NOTES_DIR, POSTS_DIR, ROOT, TRANSCRIPTS_DIR, transcript_path

NUMBERED_ID_RE = re.compile(rf"^ep-\d{{{EPISODE_NUMBER_WIDTH}}}$")
LEGACY_EP_DIR_RE = re.compile(r"^ep-\d{1,3}-")
LEGACY_BARE_FILES = frozenset({"notes.md", "post.md", "expanded.md", "transcript.md"})
PER_EPISODE_FILE_RE = re.compile(
    r"^(?P<folder>.+)\.(?P<ctype>transcript|notes|expanded|post)\.md$"
)
EXPANDED_DRAFT_RE = re.compile(r"^(?P<folder>.+)\.expanded\.draft\.md$")

EP_ID_FROM_FOLDER_RE = re.compile(r"^(ep-\d{4}|ep-special-[a-z0-9-]+)")


def _expected_id_from_folder(folder_name: str) -> str | None:
    m = EP_ID_FROM_FOLDER_RE.match(folder_name)
    return m.group(1) if m else None


def scan_frontmatter_violations() -> list[str]:
    """Validate canonical frontmatter on episode markdown under content/."""
    errors: list[str] = []
    for base in (TRANSCRIPTS_DIR, NOTES_DIR, POSTS_DIR):
        if not base.exists():
            continue
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            expected_id = _expected_id_from_folder(child.name)
            for f in child.iterdir():
                if not f.is_file() or not f.name.endswith(".md"):
                    continue
                if f.name in LEGACY_BARE_FILES:
                    continue
                ctype = infer_content_type_from_filename(f.name)
                if ctype is None:
                    continue
                text = f.read_text(encoding="utf-8")
                fm = parse_frontmatter(text)
                if not fm:
                    errors.append(f"missing frontmatter: {f.relative_to(ROOT)}")
                    continue
                errors.extend(
                    validate_frontmatter(f, fm, expected_id=expected_id)
                )
    return errors


def scan_layout_violations(rows: list[dict]) -> list[str]:
    """Return human-readable layout/id violations."""
    errors: list[str] = []

    for r in rows:
        num = r.get("episode_number")
        ep_id = r["id"]
        if num is not None:
            if not NUMBERED_ID_RE.match(ep_id):
                errors.append(
                    f"bad id format: {ep_id} (expected ep-{'0' * EPISODE_NUMBER_WIDTH}N)"
                )
            expected_id = format_episode_id(num)
            if ep_id != expected_id:
                errors.append(f"id mismatch ep {num}: catalog {ep_id} != {expected_id}")
            if r.get("transcript_status") == "complete":
                expected_tx = transcript_path(ep_id, r["slug"], num)
                if r.get("transcript_path") != expected_tx:
                    errors.append(
                        f"transcript_path mismatch {ep_id}: {r.get('transcript_path')} != {expected_tx}"
                    )

    for base in (TRANSCRIPTS_DIR, NOTES_DIR, POSTS_DIR):
        if not base.exists():
            continue
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if LEGACY_EP_DIR_RE.match(child.name):
                errors.append(f"legacy folder name: {child.relative_to(ROOT)}")
            for f in child.iterdir():
                if not f.is_file() or not f.name.endswith(".md"):
                    continue
                if f.name in LEGACY_BARE_FILES:
                    errors.append(f"legacy bare filename: {f.relative_to(ROOT)}")
                    continue
                m = PER_EPISODE_FILE_RE.match(f.name)
                if not m:
                    dm = EXPANDED_DRAFT_RE.match(f.name)
                    if dm and dm.group("folder") == child.name:
                        continue
                    if f.name == f"{child.name}.md":
                        errors.append(f"legacy transcript filename: {f.relative_to(ROOT)}")
                    else:
                        errors.append(f"unexpected file: {f.relative_to(ROOT)}")
                    continue
                if m.group("folder") != child.name:
                    errors.append(f"filename folder prefix != dir: {f.relative_to(ROOT)}")
                if m.group("ctype") not in CONTENT_TYPES:
                    errors.append(f"unknown content type in filename: {f.relative_to(ROOT)}")
    errors.extend(scan_frontmatter_violations())
    return errors
