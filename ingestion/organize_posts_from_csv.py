#!/usr/bin/env python3
"""Organize cached X posts from import/x-posts-raw.csv into content/posts/."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from vault_lib import (
    POSTS_CORPUS_PATH,
    ROOT,
    catalog_by_number,
    load_catalog,
    post_dir,
    utc_now_iso,
    write_frontmatter_md,
)
from x_posts_lib import (
    AUTO_ACCEPT_SCORE,
    POSTS_CORPUS_OTHER,
    POSTS_OTHER_DIR,
    POST_MAPPING_REVIEW,
    REVIEW_SCORE,
    X_POSTS_CSV,
    assemble_threads,
    load_csv_rows,
    match_episode,
)


def tweet_url(username: str, tweet_id: str) -> str:
    return f"https://x.com/{username}/status/{tweet_id}"


def write_other_post(unit: dict[str, Any], username: str) -> Path:
    POSTS_OTHER_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTS_OTHER_DIR / f"{unit['x_post_id']}.md"
    fm = {
        "x_post_id": unit["x_post_id"],
        "x_url": tweet_url(username, unit["x_post_id"]),
        "published_at": unit.get("created_at") or "unknown",
        "post_kind": unit.get("post_kind") or "tweet",
        "source": "x_csv",
        "imported_at": utc_now_iso(),
        "thread_root_id": unit.get("thread_root_id"),
    }
    body = unit.get("text") or ""
    return write_frontmatter_md(path, frontmatter=fm, body=body)


def write_founders_post(row: dict[str, Any], unit: dict[str, Any], username: str) -> Path:
    path = post_dir(row["id"], row["slug"]) / "post.md"
    fm: dict[str, Any] = {
        "id": row["id"],
        "title": row["title"],
        "x_url": tweet_url(username, unit["x_post_id"]),
        "x_post_id": unit["x_post_id"],
        "published_at": unit.get("created_at"),
        "source": "x_csv",
        "imported_at": utc_now_iso(),
        "post_kind": unit.get("post_kind") or "tweet",
    }
    if row.get("episode_number") is not None:
        fm["episode_number"] = row["episode_number"]
    return write_frontmatter_md(path, frontmatter=fm, body=unit.get("text") or "")


def save_review_records(records: list[dict[str, Any]]) -> None:
    POST_MAPPING_REVIEW.parent.mkdir(parents=True, exist_ok=True)
    with POST_MAPPING_REVIEW.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def regenerate_corpus(rows: list[dict[str, Any]], *, founders_only: bool = True) -> None:
    path = POSTS_CORPUS_PATH if founders_only else POSTS_CORPUS_OTHER
    path.parent.mkdir(parents=True, exist_ok=True)
    title = "All Founders posts" if founders_only else "Other X posts (non-Founders / unmapped)"
    parts = [f"# {title} (auto-generated)", "", f"Built at {utc_now_iso()}", ""]
    count = 0

    if founders_only:
        for row in sorted(rows, key=lambda r: r.get("episode_number") or 9999):
            p = post_dir(row["id"], row["slug"]) / "post.md"
            if not p.exists():
                continue
            body = p.read_text(encoding="utf-8").split("---", 2)[-1].strip()
            num = row.get("episode_number")
            label = f"#{num}" if num else row["id"]
            parts.extend([f"## {label} — {row['title']}", "", body, ""])
            count += 1
    else:
        for p in sorted(POSTS_OTHER_DIR.glob("*.md")):
            body = p.read_text(encoding="utf-8").split("---", 2)[-1].strip()
            parts.extend([f"## {p.stem}", "", body, ""])
            count += 1

    parts.insert(2, f"**Sections:** {count}")
    parts.insert(3, "")
    path.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)} ({count} sections)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize X CSV cache into vault posts")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--founders-only", action="store_true", help="Only write high-confidence Founders matches")
    args = parser.parse_args()

    if not X_POSTS_CSV.exists():
        raise SystemExit(f"Missing {X_POSTS_CSV} — run: python sync_x_cache.py --full")

    csv_rows = load_csv_rows()
    if not csv_rows:
        raise SystemExit("CSV is empty")

    from x_posts_lib import filter_attributable_rows, x_user_id

    uid = x_user_id()
    attributable = filter_attributable_rows(csv_rows, uid)
    units = assemble_threads(csv_rows, user_id=uid, attributable_only=True)
    skipped = len(csv_rows) - len(attributable)
    print(
        f"Loaded {len(csv_rows)} CSV rows ({skipped} replies-to-others skipped) "
        f"→ {len(units)} attributable units"
    )

    rows = load_catalog()
    by_number = catalog_by_number(rows)
    username = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")

    mapped = 0
    review = 0
    other = 0
    review_records: list[dict[str, Any]] = []
    seen_episodes: dict[str, str] = {}

    for unit in units:
        text = unit.get("text") or ""
        post_date = unit.get("created_at")
        row, score, reason = match_episode(text, post_date, by_number)

        if row and score >= AUTO_ACCEPT_SCORE:
            ep_id = row["id"]
            if ep_id in seen_episodes:
                continue
            if args.dry_run:
                print(f"[founders] {ep_id} score={score:.2f} — {text[:50]}...")
            else:
                write_founders_post(row, unit, username)
                seen_episodes[ep_id] = unit["x_post_id"]
            mapped += 1
        elif row and score >= REVIEW_SCORE:
            review += 1
            review_records.append(
                {
                    "x_post_id": unit["x_post_id"],
                    "suggested_episode": row["id"],
                    "episode_number": row.get("episode_number"),
                    "match_score": score,
                    "match_reason": reason,
                    "text_excerpt": text[:280],
                    "published_at": post_date,
                }
            )
            if args.dry_run:
                print(f"[review] {row['id']} score={score:.2f}")
        else:
            other += 1
            if args.dry_run:
                print(f"[other] {unit['x_post_id']} — {text[:40]}...")
            elif not args.founders_only:
                write_other_post(unit, username)

    if not args.dry_run:
        save_review_records(review_records)
        regenerate_corpus(rows, founders_only=True)
        if not args.founders_only:
            regenerate_corpus(rows, founders_only=False)

    print(f"Founders mapped: {mapped} | Review: {review} | Other: {other}")
    if review:
        print(f"Review queue → {POST_MAPPING_REVIEW.relative_to(ROOT)}")
    if other and not args.founders_only:
        print(f"Other posts → {POSTS_OTHER_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
