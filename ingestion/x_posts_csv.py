"""X post CSV cache I/O and API tweet → row conversion."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from paths import ROOT

X_POSTS_CSV = ROOT / "import" / "x-posts-raw.csv"
X_POSTS_META = ROOT / "import" / "x-posts-sync-meta.json"
POST_MAPPING_REVIEW = ROOT / "catalog" / "post-mapping-review.jsonl"
POSTS_OTHER_DIR = ROOT / "content" / "posts" / "_other"
POSTS_CORPUS_OTHER = ROOT / "content" / "posts" / "_corpus" / "all-posts-other.md"

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


def tweet_url(username: str, tweet_id: str) -> str:
    return f"https://x.com/{username}/status/{tweet_id}"


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
