"""Pending queue for X posts awaiting attribution."""

from __future__ import annotations

import json
from typing import Any

from paths import ROOT

X_POSTS_PENDING = ROOT / "catalog" / "x-posts-pending.jsonl"


def load_pending() -> list[dict[str, Any]]:
    if not X_POSTS_PENDING.exists():
        return []
    rows: list[dict[str, Any]] = []
    with X_POSTS_PENDING.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pending_ids() -> set[str]:
    return {str(r["x_post_id"]) for r in load_pending() if r.get("x_post_id")}


def unit_to_pending_record(unit: dict[str, Any], synced_at: str) -> dict[str, Any]:
    return {
        "x_post_id": unit["x_post_id"],
        "thread_root_id": unit.get("thread_root_id") or unit["x_post_id"],
        "created_at": unit.get("created_at") or "",
        "post_kind": unit.get("post_kind") or "tweet",
        "text": unit.get("text") or "",
        "synced_at": synced_at,
    }


def append_pending_units(units: list[dict[str, Any]], synced_at: str) -> int:
    if not units:
        return 0
    existing = pending_ids()
    to_add: list[dict[str, Any]] = []
    for unit in units:
        pid = unit["x_post_id"]
        if pid in existing:
            continue
        to_add.append(unit_to_pending_record(unit, synced_at))
        existing.add(pid)

    if not to_add:
        return 0

    X_POSTS_PENDING.parent.mkdir(parents=True, exist_ok=True)
    with X_POSTS_PENDING.open("a", encoding="utf-8") as f:
        for rec in to_add:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(to_add)


def save_pending(records: list[dict[str, Any]]) -> None:
    X_POSTS_PENDING.parent.mkdir(parents=True, exist_ok=True)
    with X_POSTS_PENDING.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def remove_pending_ids(ids: set[str]) -> None:
    if not ids:
        return
    remaining = [r for r in load_pending() if r.get("x_post_id") not in ids]
    save_pending(remaining)


def clear_pending() -> None:
    if X_POSTS_PENDING.exists():
        X_POSTS_PENDING.unlink()


def pending_units_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert pending JSONL lines to attribution unit dicts."""
    units: list[dict[str, Any]] = []
    for rec in records:
        units.append(
            {
                "x_post_id": rec["x_post_id"],
                "thread_root_id": rec.get("thread_root_id") or rec["x_post_id"],
                "created_at": rec.get("created_at") or None,
                "post_kind": rec.get("post_kind") or "tweet",
                "text": rec.get("text") or "",
                "part_ids": [rec["x_post_id"]],
            }
        )
    return units
