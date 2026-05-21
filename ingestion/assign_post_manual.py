#!/usr/bin/env python3
"""Write a single content/posts/{folder}/{folder}.post.md from CSV unit or raw text."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from vault_lib import (
    ROOT,
    catalog_by_number,
    load_catalog,
    post_file_path,
    utc_now_iso,
    write_frontmatter_md,
)

load_dotenv(ROOT / ".env")


def tweet_url(tweet_id: str) -> str:
    user = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")
    return f"https://x.com/{user}/status/{tweet_id}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--x-post-id", required=True)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--post-kind", default="article")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--note", help="Optional frontmatter note")
    args = parser.parse_args()

    rows = load_catalog()
    by_num = catalog_by_number(rows)
    row = by_num.get(args.episode)
    if not row:
        raise SystemExit(f"No catalog row for episode {args.episode}")

    body = args.body_file.read_text(encoding="utf-8") if args.body_file else ""
    path = post_file_path(row["id"], row["slug"], row.get("episode_number"))
    fm: dict = {
        "id": row["id"],
        "title": row["title"],
        "x_url": tweet_url(args.x_post_id),
        "x_post_id": args.x_post_id,
        "published_at": args.published_at,
        "source": "manual_attribution",
        "imported_at": utc_now_iso(),
        "post_kind": args.post_kind,
        "episode_number": args.episode,
    }
    if args.note:
        fm["attribution_note"] = args.note
    write_frontmatter_md(path, frontmatter=fm, body=body.strip())
    print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
