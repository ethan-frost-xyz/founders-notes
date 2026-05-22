#!/usr/bin/env python3
"""Write a single content/posts/{folder}/{folder}.post.md from CSV unit or raw text."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from catalog import catalog_by_number, load_catalog
from markdown_io import write_post_md
from paths import ROOT
from x_posts_lib import tweet_url

load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=int, required=True, help="Episode number (integer), not ep-NNNN id")
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
    user = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")
    path = write_post_md(
        row,
        body.strip(),
        x_url=tweet_url(user, args.x_post_id),
        x_post_id=args.x_post_id,
        published_at=args.published_at,
        source="manual_attribution",
        post_kind=args.post_kind,
        attribution_note=args.note,
    )
    print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
