#!/usr/bin/env python3
"""Sync X timeline to CSV and pending queue (windowed, API-efficient)."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import os

from dotenv import load_dotenv

from colossus import session
from markdown_io import utc_now_iso
from paths import ROOT
from x_posts_csv import (
    X_POSTS_CSV,
    append_csv_rows,
    load_existing_ids,
    load_meta,
    save_meta,
    tweet_to_row,
)
from x_posts_pending import append_pending_units
from x_posts_threads import assemble_threads
from x_sync_fetch import (
    fetch_timeline_backfill,
    fetch_timeline_windowed,
    x_bearer,
    x_user_id,
)

load_dotenv(ROOT / ".env")


def update_meta(
    meta: dict,
    *,
    user_id: str,
    existing: set[str],
    new_rows: list[dict[str, str]],
    fetched_at: str,
) -> None:
    all_ids = existing | {r["x_post_id"] for r in new_rows}
    if new_rows:
        ids_sorted = sorted(all_ids, key=int, reverse=True)
        meta.update(
            {
                "user_id": user_id,
                "newest_id": ids_sorted[0] if ids_sorted else meta.get("newest_id"),
                "oldest_id": ids_sorted[-1] if ids_sorted else meta.get("oldest_id"),
                "last_sync_at": fetched_at,
                "row_count": len(all_ids),
            }
        )
    else:
        meta["user_id"] = user_id
        meta["last_sync_at"] = fetched_at
        meta["row_count"] = len(all_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync X posts to CSV + pending queue")
    parser.add_argument("--initial-window", type=int, default=10, help="First page size (default 10)")
    parser.add_argument("--max-expansions", type=int, default=3, help="Max catch-up page expansions")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Full timeline backfill (legacy --full; max_results=100)",
    )
    parser.add_argument("--max-pages", type=int, default=100, help="Max pages for --backfill")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_ids()
    meta = load_meta()
    bearer = x_bearer()
    sess = session()
    user_id = x_user_id(sess, bearer)
    fetched_at = utc_now_iso()

    mode = "backfill" if args.backfill else "windowed"
    print(f"User {user_id} | existing rows: {len(existing)} | mode: {mode}")

    if args.backfill:
        tweets, pages = fetch_timeline_backfill(
            sess,
            bearer,
            user_id,
            max_pages=args.max_pages,
            existing_ids=existing,
            incremental=True,
        )
    else:
        since_id = meta.get("newest_id")
        tweets, pages = fetch_timeline_windowed(
            sess,
            bearer,
            user_id,
            existing_ids=existing,
            since_id=str(since_id) if since_id else None,
            initial_window=args.initial_window,
            max_expansions=args.max_expansions,
        )

    print(f"API pages: {pages} | new tweets fetched: {len(tweets)}")
    new_rows = [tweet_to_row(t, fetched_at) for t in tweets]

    if args.dry_run:
        print(f"[dry-run] would append {len(new_rows)} rows to {X_POSTS_CSV.relative_to(ROOT)}")
        return

    added = append_csv_rows(new_rows)
    update_meta(meta, user_id=user_id, existing=existing, new_rows=new_rows, fetched_at=fetched_at)
    save_meta(meta)

    uid = os.environ.get("X_USER_ID", "").strip() or user_id
    new_units: list[dict] = []
    if new_rows:
        new_units = assemble_threads(new_rows, user_id=uid, attributable_only=True)
        pending_added = append_pending_units(new_units, fetched_at)
        print(f"Pending queue +{pending_added} units")

    print(f"Appended {added} rows → {X_POSTS_CSV.relative_to(ROOT)} (total ~{len(existing) + len(new_rows)})")
    print(f"Meta → {ROOT / 'import/x-posts-sync-meta.json'}")


if __name__ == "__main__":
    main()
