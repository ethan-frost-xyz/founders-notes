#!/usr/bin/env python3
"""Scaffold empty {folder}.notes.md for episodes missing study notes."""

from __future__ import annotations

import argparse
import re

from catalog import load_catalog
from cli_args import resolve_episode_id_arg
from markdown_io import has_timestamp_datapoints, write_notes_md
from paths import ROOT, notes_file_path

SCAFFOLD_BODY = "## Raw datapoints\n"


def is_empty_scaffold(path) -> bool:
    if not path.exists():
        return False
    from markdown_io import read_markdown_body

    body = read_markdown_body(path)
    normalized = re.sub(r"\s+", " ", body)
    return normalized in ("## Raw datapoints", "## Raw datapoints ")


def eligible_rows(
    rows: list[dict],
    *,
    episode_from: int | None,
    episode_to: int | None,
    episode_id: str | None,
    missing_only: bool,
) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        num = row.get("episode_number")
        if num is None:
            continue
        if row.get("transcript_status") != "complete":
            continue
        if episode_from is not None and num < episode_from:
            continue
        if episode_to is not None and num > episode_to:
            continue
        if episode_id is not None and row["id"] != episode_id:
            continue
        ep_id = row["id"]
        slug = row["slug"]
        path = notes_file_path(ep_id, slug, num)
        if missing_only and path.exists():
            continue
        out.append(row)
    out.sort(key=lambda r: r["episode_number"] or 0)
    return out


def scaffold_row(row: dict, *, dry_run: bool, force: bool) -> tuple[str, bool]:
    """Return (status, wrote). status: created | skipped_exists | skipped_nonempty | dry_run"""
    ep_id = row["id"]
    slug = row["slug"]
    num = row["episode_number"]
    path = notes_file_path(ep_id, slug, num)

    if path.exists():
        if is_empty_scaffold(path):
            if not force:
                return "skipped_exists", False
        else:
            return "skipped_nonempty", False

    if dry_run:
        return "dry_run", False

    write_notes_md(row, SCAFFOLD_BODY, source="vault_native")
    return "created", True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold empty content/notes/{folder}/{folder}.notes.md files"
    )
    parser.add_argument("--from", dest="episode_from", type=int, help="Min episode number")
    parser.add_argument("--to", dest="episode_to", type=int, help="Max episode number")
    parser.add_argument("--id", dest="episode_id", help="Single episode id, e.g. ep-0200")
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Only episodes without an existing .notes.md file",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Print path to first missing notes file (by episode number) and exit",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing empty scaffolds only (never overwrite notes with bullets)",
    )
    args = parser.parse_args()

    if args.next:
        args.episode_from = args.episode_from or 190
    if not any([args.episode_from, args.episode_to, args.episode_id]) and not args.next:
        args.episode_from = 190
        args.missing = True

    rows = load_catalog()
    episode_id = args.episode_id
    if episode_id:
        resolve_episode_id_arg(rows, episode_id)

    selected = eligible_rows(
        rows,
        episode_from=args.episode_from,
        episode_to=args.episode_to,
        episode_id=episode_id,
        missing_only=args.missing and not args.next,
    )

    if args.next:
        for row in selected:
            ep_id = row["id"]
            slug = row["slug"]
            num = row["episode_number"]
            path = notes_file_path(ep_id, slug, num)
            if not path.exists() or not has_timestamp_datapoints(path):
                rel = path.relative_to(ROOT)
                print(rel)
                return
        raise SystemExit("No episode in selection needs notes (all have datapoints)")

    created = 0
    skipped_exists = 0
    skipped_nonempty = 0
    dry_run = 0

    for row in selected:
        status, wrote = scaffold_row(row, dry_run=args.dry_run, force=args.force)
        if wrote:
            created += 1
            rel = notes_file_path(row["id"], row["slug"], row["episode_number"]).relative_to(ROOT)
            print(f"  wrote {rel}")
        elif status == "dry_run":
            dry_run += 1
        elif status == "skipped_exists":
            skipped_exists += 1
        elif status == "skipped_nonempty":
            skipped_nonempty += 1

    print(f"Selected {len(selected)} episode(s)")
    if args.dry_run:
        print(f"Would create {dry_run} scaffold(s)")
    else:
        print(f"Created {created} | skipped (exists) {skipped_exists} | skipped (has content) {skipped_nonempty}")


if __name__ == "__main__":
    main()
