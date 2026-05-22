#!/usr/bin/env python3
"""Fetch X posts into append-only import/x-posts-raw.csv (incremental, API-efficient)."""

from __future__ import annotations

import argparse
import os
from typing import Any

from dotenv import load_dotenv

from colossus import session
from markdown_io import utc_now_iso
from paths import ROOT
from x_posts_lib import (
    X_POSTS_CSV,
    append_csv_rows,
    load_existing_ids,
    load_meta,
    save_meta,
    tweet_to_row,
)

load_dotenv(ROOT / ".env")

X_API = "https://api.twitter.com/2"
TWEET_FIELDS = (
    "created_at,conversation_id,referenced_tweets,attachments,entities,"
    "note_tweet,public_metrics,in_reply_to_user_id"
)


def x_bearer() -> str:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set X_BEARER_TOKEN in .env")
    return token


def x_user_id(sess, bearer: str) -> str:
    uid = os.environ.get("X_USER_ID", "").strip()
    if uid:
        return uid
    username = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")
    resp = sess.get(
        f"{X_API}/users/by/username/{username}",
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json().get("data")
    if not data:
        raise SystemExit(f"Could not resolve X user @{username}")
    return data["id"]


def fetch_timeline(
    sess,
    bearer: str,
    user_id: str,
    *,
    max_pages: int,
    existing_ids: set[str],
    incremental: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Returns (new_tweets, pages_fetched)."""
    collected: list[dict[str, Any]] = []
    pages = 0
    next_token: str | None = None
    hit_known = False

    while pages < max_pages and not hit_known:
        params: dict[str, Any] = {
            "max_results": 100,
            "tweet.fields": TWEET_FIELDS,
            "exclude": "retweets",
        }
        if next_token:
            params["pagination_token"] = next_token

        resp = sess.get(
            f"{X_API}/users/{user_id}/tweets",
            headers={"Authorization": f"Bearer {bearer}"},
            params=params,
            timeout=60,
        )
        if resp.status_code == 429:
            raise SystemExit("X API rate limited — try again later")
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        pages += 1

        for tweet in batch:
            tid = tweet["id"]
            if tid in existing_ids:
                if incremental:
                    hit_known = True
                    break
                continue
            collected.append(tweet)

        if hit_known:
            break
        meta = payload.get("meta") or {}
        next_token = meta.get("next_token")
        if not next_token:
            break

    return collected, pages


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync X posts to import/x-posts-raw.csv")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Backfill entire timeline (ignore incremental stop)",
    )
    parser.add_argument("--max-pages", type=int, default=100, help="Max API pages per run")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write CSV")
    args = parser.parse_args()

    existing = load_existing_ids()
    meta = load_meta()
    incremental = not args.full

    bearer = x_bearer()
    sess = session()
    user_id = x_user_id(sess, bearer)
    fetched_at = utc_now_iso()

    print(f"User {user_id} | existing rows: {len(existing)} | mode: {'incremental' if incremental else 'full'}")

    tweets, pages = fetch_timeline(
        sess,
        bearer,
        user_id,
        max_pages=args.max_pages,
        existing_ids=existing,
        incremental=incremental,
    )
    print(f"API pages: {pages} | new tweets fetched: {len(tweets)}")

    new_rows = [tweet_to_row(t, fetched_at) for t in tweets]
    if args.dry_run:
        print(f"[dry-run] would append {len(new_rows)} rows to {X_POSTS_CSV.relative_to(ROOT)}")
        return

    added = append_csv_rows(new_rows)
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

    save_meta(meta)
    print(f"Appended {added} rows → {X_POSTS_CSV.relative_to(ROOT)} (total ~{len(all_ids)})")
    print(f"Meta → {ROOT / 'import/x-posts-sync-meta.json'}")


if __name__ == "__main__":
    main()
