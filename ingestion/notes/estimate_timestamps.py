#!/usr/bin/env python3
"""Estimate MM:SS prefixes for notes bullets missing timestamps."""

from __future__ import annotations

import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse

from catalog import load_catalog, resolve_catalog_row
from cli_args import resolve_episode_id_arg
from gaps_report import count_phase2_coverage
from markdown_io import read_markdown_body, split_markdown_parts, write_frontmatter_md
from paths import ROOT, notes_file_path, transcript_path
from timestamp_estimate import (
    apply_estimates_to_notes_body,
    estimate_bullet_timestamp,
    iter_lost_timestamp_bullets,
)


def _episodes_missing_timestamps(rows: list[dict]) -> list[dict]:
    _, _, _, _, _, _, missing_ts = count_phase2_coverage(rows)
    nums = {num for num, _ in missing_ts}
    return [r for r in rows if r.get("episode_number") in nums]


def _process_episode(
    row: dict,
    *,
    min_confidence: float,
    apply: bool,
) -> list:
    ep_id = row["id"]
    slug = row["slug"]
    num = row["episode_number"]
    duration = row.get("duration_seconds")
    npath = notes_file_path(ep_id, slug, num)
    tpath = ROOT / transcript_path(ep_id, slug, num)
    if not npath.is_file():
        return []
    if not tpath.is_file():
        print(f"  {ep_id}: skip — no transcript", file=sys.stderr)
        return []
    notes_body = read_markdown_body(npath)
    bullets = iter_lost_timestamp_bullets(notes_body)
    if not bullets:
        return []
    transcript_body = read_markdown_body(tpath)
    if duration is None:
        print(f"  {ep_id}: skip — no duration_seconds in catalog", file=sys.stderr)
        return []

    estimates = [
        estimate_bullet_timestamp(
            text,
            line=line,
            transcript_body=transcript_body,
            duration_seconds=int(duration),
            min_confidence=min_confidence,
        )
        for line, text in bullets
    ]

    for est in estimates:
        status = est.suggested or f"SKIP ({est.reason})"
        print(f"  {ep_id}  conf={est.confidence:.2f}  {status}  {est.bullet_text[:60]}")

    if apply:
        raw = npath.read_text(encoding="utf-8")
        body = read_markdown_body(npath)
        new_body = apply_estimates_to_notes_body(body, estimates)
        if new_body != body:
            fm, _ = split_markdown_parts(raw)
            fm = fm or {}
            write_frontmatter_md(npath, frontmatter=fm, body=new_body)
            print(f"  {ep_id}: wrote {npath.relative_to(_bootstrap.resolve_vault_root())}")

    return estimates


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate timestamps for lost-timestamp note bullets")
    parser.add_argument("--id", metavar="ep-NNNN", help="Single episode")
    parser.add_argument("--all-missing", action="store_true", help="All episodes in gaps missing-timestamp list")
    parser.add_argument("--apply", action="store_true", help="Write .notes.md (default is dry-run)")
    parser.add_argument("--min-confidence", type=float, default=0.35, help="Minimum match confidence")
    args = parser.parse_args()

    if not args.id and not args.all_missing:
        parser.error("Specify --id or --all-missing")

    rows = load_catalog()
    if args.id:
        row = resolve_episode_id_arg(rows, args.id)
        if row is None:
            raise SystemExit(f"Episode not in catalog: {args.id}")
        targets = [row]
    else:
        targets = _episodes_missing_timestamps(rows)

    print(f"{'Applying' if args.apply else 'Dry-run'}: {len(targets)} episode(s)")
    for row in targets:
        _process_episode(row, min_confidence=args.min_confidence, apply=args.apply)


if __name__ == "__main__":
    main()
