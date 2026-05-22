"""Filesystem layout and catalog id consistency checks."""

from __future__ import annotations

import re

from episode_ids import EPISODE_NUMBER_WIDTH, format_episode_id
from paths import CONTENT_TYPES, NOTES_DIR, POSTS_DIR, ROOT, TRANSCRIPTS_DIR, transcript_path

NUMBERED_ID_RE = re.compile(rf"^ep-\d{{{EPISODE_NUMBER_WIDTH}}}$")
LEGACY_EP_DIR_RE = re.compile(r"^ep-\d{1,3}-")
LEGACY_BARE_FILES = frozenset({"notes.md", "post.md", "expanded.md", "transcript.md"})
PER_EPISODE_FILE_RE = re.compile(
    r"^(?P<folder>.+)\.(?P<ctype>transcript|notes|expanded|post)\.md$"
)


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
                    if f.name == f"{child.name}.md":
                        errors.append(f"legacy transcript filename: {f.relative_to(ROOT)}")
                    else:
                        errors.append(f"unexpected file: {f.relative_to(ROOT)}")
                    continue
                if m.group("folder") != child.name:
                    errors.append(f"filename folder prefix != dir: {f.relative_to(ROOT)}")
                if m.group("ctype") not in CONTENT_TYPES:
                    errors.append(f"unknown content type in filename: {f.relative_to(ROOT)}")
    return errors
