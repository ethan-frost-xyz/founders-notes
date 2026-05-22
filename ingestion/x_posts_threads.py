"""X post thread grouping and attribution filters."""

from __future__ import annotations

import os
from typing import Any

from x_posts_csv import load_meta


def x_user_id() -> str:
    uid = os.environ.get("X_USER_ID", "").strip()
    if uid:
        return uid
    meta = load_meta()
    if meta.get("user_id"):
        return str(meta["user_id"])
    raise RuntimeError("Set X_USER_ID in .env or ensure x-posts-sync-meta.json has user_id")


def is_reply_to_other(row: dict[str, str], user_id: str) -> bool:
    """Reply to someone else's thread — not your standalone Founders post."""
    if row.get("post_kind") != "reply":
        return False
    target = (row.get("in_reply_to_user_id") or "").strip()
    return bool(target and target != user_id)


def is_attributable_row(row: dict[str, str], user_id: str) -> bool:
    return not is_reply_to_other(row, user_id)


def is_article_unit(unit: dict[str, Any]) -> bool:
    """Native X article (note_tweet). Not mapped by organize — use assign_post_manual."""
    return (unit.get("post_kind") or "").strip().lower() == "article"


def filter_attributable_rows(rows: list[dict[str, str]], user_id: str | None = None) -> list[dict[str, str]]:
    uid = user_id or x_user_id()
    return [r for r in rows if is_attributable_row(r, uid)]


def assemble_threads(
    rows: list[dict[str, str]],
    *,
    user_id: str | None = None,
    attributable_only: bool = True,
) -> list[dict[str, Any]]:
    """Group CSV rows into publishable units (your roots + self-thread replies only)."""
    uid = user_id or x_user_id()
    work = filter_attributable_rows(rows, uid) if attributable_only else rows

    by_root: dict[str, list[dict[str, str]]] = {}
    for row in work:
        root = row.get("thread_root_id") or row["x_post_id"]
        by_root.setdefault(root, []).append(row)

    units: list[dict[str, Any]] = []
    for root_id, parts in by_root.items():
        parts.sort(key=lambda r: r.get("created_at") or "")
        root_rows = [
            p
            for p in parts
            if p.get("is_thread_root") == "true" and is_attributable_row(p, uid)
        ]
        if not root_rows:
            continue
        root = root_rows[0]
        if is_reply_to_other(root, uid):
            continue
        texts: list[str] = []
        seen: set[str] = set()
        for p in parts:
            if not is_attributable_row(p, uid):
                continue
            t = (p.get("text") or "").strip()
            if t and t not in seen:
                texts.append(t)
                seen.add(t)
        if not texts:
            continue
        units.append(
            {
                "thread_root_id": root_id,
                "x_post_id": root["x_post_id"],
                "created_at": root.get("created_at", "")[:10] or None,
                "post_kind": root.get("post_kind") or "tweet",
                "conversation_id": root.get("conversation_id") or root_id,
                "text": "\n\n".join(texts),
                "part_ids": [p["x_post_id"] for p in parts if is_attributable_row(p, uid)],
            }
        )
    units.sort(key=lambda u: u.get("created_at") or "", reverse=True)
    return units
