#!/usr/bin/env python3
"""Merge itunes:duration from RSS into existing catalog/episodes.jsonl rows."""

from __future__ import annotations

import sys
from pathlib import Path

_PIPELINE = Path(__file__).resolve().parent
_INGESTION = _PIPELINE.parent
for _p in (_INGESTION, _PIPELINE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse

from build_catalog import load_rss_meta
from catalog import load_catalog, save_catalog
from colossus import session


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill duration_seconds from podcast RSS")
    parser.add_argument("--dry-run", action="store_true", help="Print counts only")
    args = parser.parse_args()

    rows = load_catalog()
    if not rows:
        raise SystemExit("catalog/episodes.jsonl is empty — run build_catalog.py first")

    sess = session()
    rss_meta = load_rss_meta(sess)
    updated = 0
    missing = 0

    for row in rows:
        num = row.get("episode_number")
        duration = None
        if num is not None and num in rss_meta:
            duration = rss_meta[num].get("duration_seconds")
        if duration is None:
            title = (row.get("title") or "").lower()
            if title in rss_meta:
                duration = rss_meta[title].get("duration_seconds")
        if duration is None:
            missing += 1
            continue
        if row.get("duration_seconds") != duration:
            row["duration_seconds"] = duration
            updated += 1

    print(f"Updated duration_seconds on {updated} row(s); {missing} without RSS duration")
    if not args.dry_run and updated:
        save_catalog(rows)
        print("Saved catalog")


if __name__ == "__main__":
    main()
