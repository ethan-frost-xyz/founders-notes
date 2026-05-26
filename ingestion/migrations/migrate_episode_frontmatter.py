#!/usr/bin/env python3
"""Backfill canonical episode frontmatter on all content/ markdown (body preserved)."""

from __future__ import annotations

import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
from collections import Counter

from catalog import load_catalog
from layout import EP_ID_FROM_FOLDER_RE
from markdown_io import (
    body_hash,
    infer_content_type_from_filename,
    normalize_frontmatter_from_existing,
    parse_frontmatter,
    rewrite_frontmatter_preserving_body,
    serialize_frontmatter,
    split_markdown_parts,
)
from paths import NOTES_DIR, POSTS_DIR, ROOT, TRANSCRIPTS_DIR

CONTENT_GLOBS: tuple[tuple[Path, str], ...] = (
    (TRANSCRIPTS_DIR, "**/*.transcript.md"),
    (NOTES_DIR, "**/*.notes.md"),
    (NOTES_DIR, "**/*.expanded.md"),
    (NOTES_DIR, "**/*.expanded.draft.md"),
    (POSTS_DIR, "**/*.post.md"),
)


def catalog_by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def resolve_row(
    path: Path,
    existing: dict[str, str],
    by_id: dict[str, dict],
) -> dict | None:
    ep_id = existing.get("id")
    if ep_id and ep_id in by_id:
        return by_id[ep_id]
    m = EP_ID_FROM_FOLDER_RE.match(path.parent.name)
    if m and m.group(1) in by_id:
        return by_id[m.group(1)]
    return None


def iter_episode_markdown() -> list[Path]:
    files: list[Path] = []
    for base, pattern in CONTENT_GLOBS:
        if not base.exists():
            continue
        files.extend(sorted(base.glob(pattern)))
    return files


def current_frontmatter_block(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return "---" + parts[1] + "---"


def migrate_file(path: Path, row: dict, *, apply: bool) -> str:
    """Returns status: updated, unchanged, or skipped."""
    content_type = infer_content_type_from_filename(path.name)
    if content_type is None:
        return "skipped"
    text = path.read_text(encoding="utf-8")
    existing = parse_frontmatter(text)
    if not existing:
        return "skipped"
    new_fm = normalize_frontmatter_from_existing(row, existing, content_type)
    new_block = serialize_frontmatter(new_fm)
    old_block = current_frontmatter_block(text)
    if old_block == new_block:
        return "unchanged"
    _, body = split_markdown_parts(text)
    before_hash = body_hash(body)
    if apply:
        rewrite_frontmatter_preserving_body(path, frontmatter=new_fm)
        _, after_body = split_markdown_parts(path.read_text(encoding="utf-8"))
        if body_hash(after_body) != before_hash:
            raise SystemExit(f"BODY CHANGED: {path.relative_to(ROOT)}")
    return "updated"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill canonical frontmatter on content/ episode markdown"
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--apply", action="store_true", help="Rewrite frontmatter in place")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    rows = load_catalog()
    by_id = catalog_by_id(rows)
    counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    unmapped: list[str] = []

    for path in iter_episode_markdown():
        existing = parse_frontmatter(path.read_text(encoding="utf-8"))
        content_type = infer_content_type_from_filename(path.name) or "unknown"
        row = resolve_row(path, existing, by_id)
        if row is None:
            unmapped.append(str(path.relative_to(ROOT)))
            counts["unmapped"] += 1
            type_counts[f"{content_type}:unmapped"] += 1
            continue
        status = migrate_file(path, row, apply=args.apply)
        if not args.apply and status == "updated":
            status = "would_update"
        counts[status] += 1
        type_counts[f"{content_type}:{status}"] += 1

    print(f"Files scanned: {sum(counts.values())}")
    for key, n in sorted(counts.items()):
        print(f"  {key}: {n}")
    print("\nBy content type:")
    for key, n in sorted(type_counts.items()):
        print(f"  {key}: {n}")
    if unmapped:
        print(f"\nUnmapped ({len(unmapped)}):")
        for u in unmapped[:20]:
            print(f"  {u}")
        if len(unmapped) > 20:
            print(f"  ... and {len(unmapped) - 20} more")
    if args.dry_run:
        print("\n(dry-run — no files modified)")
    else:
        print("\nApplied frontmatter backfill.")


if __name__ == "__main__":
    main()
