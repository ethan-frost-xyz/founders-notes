#!/usr/bin/env python3
"""Import X posts via API v2 into content/posts/{folder}/post.md."""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from vault_lib import (
    IMPORT_REVIEW_PATH,
    POSTS_CORPUS_PATH,
    ROOT,
    catalog_by_number,
    load_catalog,
    post_dir,
    save_unmapped_posts,
    session,
    write_post_md,
)

load_dotenv(ROOT / ".env")

X_API = "https://api.twitter.com/2"
EP_MENTION_RE = re.compile(r"(?:#|ep(?:isode)?\s*)(\d{1,3})\b", re.IGNORECASE)
AUTO_ACCEPT_SCORE = 0.75


def x_bearer() -> str:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set X_BEARER_TOKEN in .env (X Developer Portal → Bearer Token)")
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


def fetch_all_tweets(sess, bearer: str, user_id: str, max_pages: int = 50) -> list[dict[str, Any]]:
    tweets: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "max_results": 100,
        "tweet.fields": "created_at,conversation_id,referenced_tweets,attachments,entities",
        "expansions": "referenced_tweets.id,attachments.media_keys",
        "exclude": "retweets",
    }
    url = f"{X_API}/users/{user_id}/tweets"
    pages = 0
    while url and pages < max_pages:
        resp = sess.get(
            url,
            headers={"Authorization": f"Bearer {bearer}"},
            params=params if pages == 0 else None,
            timeout=60,
        )
        if resp.status_code == 429:
            raise SystemExit("X API rate limited — try again later")
        resp.raise_for_status()
        payload = resp.json()
        tweets.extend(payload.get("data") or [])
        meta = payload.get("meta") or {}
        next_token = meta.get("next_token")
        if not next_token:
            break
        params = {"pagination_token": next_token}
        pages += 1
    return tweets


def fetch_thread_replies(sess, bearer: str, conversation_id: str, author_id: str) -> list[str]:
    """Self-replies in the same conversation by the author."""
    resp = sess.get(
        f"{X_API}/tweets/search/recent",
        headers={"Authorization": f"Bearer {bearer}"},
        params={
            "query": f"conversation_id:{conversation_id} from:{author_id}",
            "max_results": 100,
            "tweet.fields": "created_at,author_id",
        },
        timeout=60,
    )
    if resp.status_code != 200:
        return []
    parts = []
    for t in sorted(resp.json().get("data") or [], key=lambda x: x.get("created_at", "")):
        text = t.get("text", "").strip()
        if text:
            parts.append(text)
    return parts


def parse_post_date(iso: str | None) -> str | None:
    if not iso:
        return None
    return iso[:10]


def days_between(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        da = datetime.strptime(a, "%Y-%m-%d")
        db = datetime.strptime(b, "%Y-%m-%d")
        return abs((da - db).days)
    except ValueError:
        return None


def title_tokens(title: str) -> set[str]:
    """Lowercase tokens from title for fuzzy match (skip #N prefix)."""
    t = re.sub(r"^#\d+[:\s]+", "", title, flags=re.IGNORECASE)
    words = re.findall(r"[a-z]{4,}", t.lower())
    return set(words)


def match_episode(
    text: str,
    post_date: str | None,
    rows_by_number: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, float, str]:
    """Return (catalog_row, confidence, reason)."""
    mentions = [int(m.group(1)) for m in EP_MENTION_RE.finditer(text)]
    if mentions:
        num = mentions[0]
        row = rows_by_number.get(num)
        if row:
            return row, 0.95, f"explicit_mention_{num}"

    text_lower = text.lower()
    best: tuple[dict[str, Any] | None, float, str] = (None, 0.0, "none")

    for num, row in rows_by_number.items():
        title = row.get("title") or ""
        tokens = title_tokens(title)
        if not tokens:
            continue
        hits = sum(1 for tok in tokens if tok in text_lower)
        if hits >= 2:
            score = min(0.7, 0.35 + hits * 0.1)
            pub = row.get("published_at")
            delta = days_between(post_date, pub)
            if delta is not None and delta <= 14:
                score = min(0.85, score + 0.2)
            if score > best[1]:
                best = (row, score, f"title_tokens_{hits}")

    if best[0] and post_date:
        row = best[0]
        delta = days_between(post_date, row.get("published_at"))
        if delta is not None and delta <= 7 and best[1] < 0.8:
            return row, 0.72, "date_proximity"

    return best


def tweet_url(author: str, tweet_id: str) -> str:
    return f"https://x.com/{author}/status/{tweet_id}"


def regenerate_corpus(rows: list[dict[str, Any]]) -> None:
    POSTS_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "# All Founders posts (auto-generated)",
        "",
        "Regenerated by `import_posts_x.py`. Section per episode for grep and LLM recall.",
        "",
    ]
    posts_written = []
    for row in sorted(rows, key=lambda r: r.get("episode_number") or 9999):
        ep_id = row["id"]
        slug = row["slug"]
        path = post_dir(ep_id, slug) / "post.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        body = text.split("---", 2)[-1].strip() if "---" in text else text
        num = row.get("episode_number")
        label = f"#{num}" if num else ep_id
        parts.append(f"## {label} — {row['title']}")
        parts.append("")
        parts.append(body)
        parts.append("")
        posts_written.append(ep_id)

    parts.insert(3, f"**Episodes with posts:** {len(posts_written)}")
    parts.insert(4, "")
    POSTS_CORPUS_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {POSTS_CORPUS_PATH.relative_to(ROOT)} ({len(posts_written)} sections)")


def import_google_doc(path: Path, rows_by_number: dict[int, dict[str, Any]], dry_run: bool) -> int:
    """Optional secondary source: section-split by episode number."""
    text = path.read_text(encoding="utf-8")
    count = 0
    current_num: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal count
        if current_num is None or not buffer:
            return
        row = rows_by_number.get(current_num)
        if not row:
            return
        body = "\n".join(buffer).strip()
        if not body:
            return
        if not dry_run:
            slug = row["slug"]
            p = post_dir(row["id"], slug) / "post.md"
            if not p.exists():
                write_post_md(
                    row,
                    body,
                    x_url="",
                    x_post_id=f"google_doc_{current_num}",
                    source="google_doc",
                )
                count += 1

    for line in text.splitlines():
        m = EP_MENTION_RE.search(line) or re.match(r"^#?\s*(\d{1,3})\b", line.strip())
        if m and not line.strip().startswith("-") and len(line.strip()) < 120:
            flush()
            buffer = []
            current_num = int(m.group(1))
            continue
        if current_num is not None:
            buffer.append(line)
    flush()
    return count


def update_import_review_x(mapped: int, unmapped: int, low_confidence: list[tuple[str, float]]) -> None:
    content = (
        IMPORT_REVIEW_PATH.read_text(encoding="utf-8")
        if IMPORT_REVIEW_PATH.exists()
        else "# Import review\n"
    )
    section = [
        "",
        "## X import (last run)",
        "",
        f"- Mapped: {mapped}",
        f"- Unmapped: {unmapped}",
    ]
    if low_confidence:
        section.append(f"- Low confidence (manual check): {len(low_confidence)}")
        for tid, score in low_confidence[:20]:
            section.append(f"  - `{tid}` — score {score:.2f}")
    new_content = content + "\n".join(section) + "\n"
    IMPORT_REVIEW_PATH.write_text(new_content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import X posts into content/posts/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--doc", type=Path, help="Optional Google Doc export for gaps")
    parser.add_argument("--corpus-only", action="store_true", help="Only regenerate all-posts.md")
    args = parser.parse_args()

    rows = load_catalog()
    rows_by_number = catalog_by_number(rows)
    if args.corpus_only:
        regenerate_corpus(rows)
        return

    bearer = x_bearer()
    sess = session()
    user_id = x_user_id(sess, bearer)
    username = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")

    print(f"Fetching tweets for user {user_id} ...")
    tweets = fetch_all_tweets(sess, bearer, user_id, max_pages=args.max_pages)
    print(f"Fetched {len(tweets)} top-level tweets")

    mapped = 0
    unmapped = 0
    unmapped_records: list[dict[str, Any]] = []
    low_confidence: list[tuple[str, float]] = []
    seen_episodes: dict[str, str] = {}

    for tweet in tweets:
        tweet_id = tweet["id"]
        text = tweet.get("text", "")
        post_date = parse_post_date(tweet.get("created_at"))
        row, score, reason = match_episode(text, post_date, rows_by_number)

        body_parts = [text]
        conv_id = tweet.get("conversation_id")
        if conv_id and conv_id != tweet_id:
            replies = fetch_thread_replies(sess, bearer, conv_id, user_id)
            for r in replies:
                if r not in body_parts:
                    body_parts.append(r)
        body = "\n\n".join(body_parts)

        url = tweet_url(username, tweet_id)

        if row is None or score < AUTO_ACCEPT_SCORE:
            unmapped += 1
            rec = {
                "x_post_id": tweet_id,
                "x_url": url,
                "published_at": post_date,
                "text_excerpt": text[:280],
                "match_score": score,
                "match_reason": reason,
            }
            unmapped_records.append(rec)
            continue

        if score < 0.85:
            low_confidence.append((tweet_id, score))

        ep_id = row["id"]
        if ep_id in seen_episodes and not args.dry_run:
            # Keep longer post if duplicate match
            existing_path = post_dir(ep_id, row["slug"]) / "post.md"
            if existing_path.exists() and len(body) <= len(existing_path.read_text(encoding="utf-8")):
                continue

        if args.dry_run:
            print(f"[dry-run] {ep_id} score={score:.2f} ({reason}) — {text[:60]}...")
            mapped += 1
            continue

        write_post_md(
            row,
            body,
            x_url=url,
            x_post_id=tweet_id,
            published_at=post_date,
        )
        seen_episodes[ep_id] = tweet_id
        mapped += 1

    if not args.dry_run:
        save_unmapped_posts(unmapped_records)
        regenerate_corpus(rows)
    elif unmapped_records:
        print(f"[dry-run] would write {len(unmapped_records)} unmapped posts")

    if args.doc and args.doc.exists():
        doc_count = import_google_doc(args.doc, rows_by_number, args.dry_run)
        print(f"Google Doc fallback: {doc_count} posts")
        if not args.dry_run:
            regenerate_corpus(rows)

    update_import_review_x(mapped, unmapped, low_confidence)
    print(f"Mapped: {mapped} | Unmapped: {unmapped}")
    if unmapped:
        print(f"See {ROOT / 'catalog/unmapped-posts.jsonl'}")


if __name__ == "__main__":
    main()
