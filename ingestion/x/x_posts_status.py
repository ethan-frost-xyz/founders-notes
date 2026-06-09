#!/usr/bin/env python3
"""Zero-API status for X post sync and vault coverage."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse

from x_posts_chrono import vault_max_episode
from x_posts_csv import X_POSTS_CSV, load_meta
from x_posts_pending import load_pending


def newest_csv_id() -> str | None:
    if not X_POSTS_CSV.exists():
        return None
    import csv

    newest: str | None = None
    with X_POSTS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tid = row.get("x_post_id")
            if tid and (newest is None or int(tid) > int(newest)):
                newest = tid
    return newest


def main() -> None:
    parser = argparse.ArgumentParser(description="X posts pipeline status (no API)")
    parser.add_argument(
        "--expect-episode",
        type=int,
        help="Exit 1 if vault max post episode is below N",
    )
    args = parser.parse_args()

    meta = load_meta()
    max_ep = vault_max_episode()
    pending_n = len(load_pending())
    last_sync = meta.get("last_sync_at") or "never"
    newest = meta.get("newest_id") or newest_csv_id() or "none"

    print(f"Vault max post episode: ep-{max_ep:04d}" if max_ep else "Vault max post episode: none")
    print(f"Pending units: {pending_n}")
    print(f"Last sync: {last_sync}")
    print(f"Newest cached tweet id: {newest}")

    if args.expect_episode is not None and max_ep < args.expect_episode:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
