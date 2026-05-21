"""Shared helpers for X post cache and organization."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from vault_lib import ROOT, utc_now_iso

X_POSTS_CSV = ROOT / "import" / "x-posts-raw.csv"
X_POSTS_META = ROOT / "import" / "x-posts-sync-meta.json"
POST_MAPPING_REVIEW = ROOT / "catalog" / "post-mapping-review.jsonl"
POSTS_OTHER_DIR = ROOT / "content" / "posts" / "_other"
POSTS_CORPUS_OTHER = ROOT / "content" / "posts" / "_corpus" / "all-posts-other.md"

EP_MENTION_RE = re.compile(r"(?:#|ep(?:isode)?\s*)(\d{1,3})\b", re.IGNORECASE)
AUTO_ACCEPT_SCORE = 0.75
REVIEW_SCORE = 0.5

CSV_COLUMNS = [
    "x_post_id",
    "created_at",
    "text",
    "post_kind",
    "conversation_id",
    "in_reply_to_user_id",
    "referenced_tweets",
    "attachments",
    "public_metrics",
    "entities",
    "thread_root_id",
    "is_thread_root",
    "fetched_at",
]


def load_existing_ids() -> set[str]:
    if not X_POSTS_CSV.exists():
        return set()
    ids: set[str] = set()
    with X_POSTS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("x_post_id"):
                ids.add(row["x_post_id"])
    return ids


def load_meta() -> dict[str, Any]:
    if not X_POSTS_META.exists():
        return {}
    return json.loads(X_POSTS_META.read_text(encoding="utf-8"))


def save_meta(meta: dict[str, Any]) -> None:
    X_POSTS_META.parent.mkdir(parents=True, exist_ok=True)
    X_POSTS_META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def append_csv_rows(rows: list[dict[str, str]]) -> int:
    if not rows:
        return 0
    X_POSTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not X_POSTS_CSV.exists() or X_POSTS_CSV.stat().st_size == 0
    with X_POSTS_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def json_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def extract_text(tweet: dict[str, Any]) -> str:
    note = tweet.get("note_tweet")
    if isinstance(note, dict) and note.get("text"):
        return note["text"].strip()
    return (tweet.get("text") or "").strip()


def classify_post_kind(tweet: dict[str, Any]) -> str:
    if tweet.get("note_tweet"):
        return "article"
    refs = tweet.get("referenced_tweets") or []
    for ref in refs:
        if ref.get("type") == "replied_to":
            return "reply"
        if ref.get("type") == "quoted":
            return "quote"
    if tweet.get("in_reply_to_user_id"):
        return "reply"
    return "tweet"


def thread_root_id(tweet: dict[str, Any]) -> str:
    tid = tweet["id"]
    conv = tweet.get("conversation_id") or tid
    refs = tweet.get("referenced_tweets") or []
    for ref in refs:
        if ref.get("type") == "replied_to":
            return conv
    return tid if conv == tid else conv


def is_thread_root(tweet: dict[str, Any]) -> bool:
    return tweet["id"] == thread_root_id(tweet)


def tweet_to_row(tweet: dict[str, Any], fetched_at: str) -> dict[str, str]:
    root = thread_root_id(tweet)
    return {
        "x_post_id": tweet["id"],
        "created_at": tweet.get("created_at") or "",
        "text": extract_text(tweet),
        "post_kind": classify_post_kind(tweet),
        "conversation_id": tweet.get("conversation_id") or tweet["id"],
        "in_reply_to_user_id": tweet.get("in_reply_to_user_id") or "",
        "referenced_tweets": json_field(tweet.get("referenced_tweets")),
        "attachments": json_field(tweet.get("attachments")),
        "public_metrics": json_field(tweet.get("public_metrics")),
        "entities": json_field(tweet.get("entities")),
        "thread_root_id": root,
        "is_thread_root": "true" if is_thread_root(tweet) else "false",
        "fetched_at": fetched_at,
    }


def load_csv_rows() -> list[dict[str, str]]:
    if not X_POSTS_CSV.exists():
        return []
    with X_POSTS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def days_between(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        da = datetime.strptime(a[:10], "%Y-%m-%d")
        db = datetime.strptime(b[:10], "%Y-%m-%d")
        return abs((da - db).days)
    except ValueError:
        return None


def title_tokens(title: str) -> set[str]:
    t = re.sub(r"^#\d+[:\s]+", "", title, flags=re.IGNORECASE)
    return set(re.findall(r"[a-z]{4,}", t.lower()))


def match_episode(
    text: str,
    post_date: str | None,
    rows_by_number: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, float, str]:
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


def assemble_threads(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Group CSV rows into publishable units (thread roots + merged text)."""
    by_root: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        root = row.get("thread_root_id") or row["x_post_id"]
        by_root.setdefault(root, []).append(row)

    units: list[dict[str, Any]] = []
    for root_id, parts in by_root.items():
        parts.sort(key=lambda r: r.get("created_at") or "")
        root_rows = [p for p in parts if p.get("is_thread_root") == "true"]
        if not root_rows:
            root_rows = [parts[0]]
        root = root_rows[0]
        texts: list[str] = []
        seen: set[str] = set()
        for p in parts:
            t = (p.get("text") or "").strip()
            if t and t not in seen:
                texts.append(t)
                seen.add(t)
        units.append(
            {
                "thread_root_id": root_id,
                "x_post_id": root["x_post_id"],
                "created_at": root.get("created_at", "")[:10] or None,
                "post_kind": root.get("post_kind") or "tweet",
                "conversation_id": root.get("conversation_id") or root_id,
                "text": "\n\n".join(texts),
                "part_ids": [p["x_post_id"] for p in parts],
            }
        )
    units.sort(key=lambda u: u.get("created_at") or "", reverse=True)
    return units
