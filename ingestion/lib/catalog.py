"""Catalog JSONL load/save and row lookup."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from episode_ids import make_id
from paths import CATALOG_PATH


def _jsonl_cache_key(path: Path | str | None) -> str:
    p = Path(path) if path is not None else CATALOG_PATH
    try:
        return str(p.resolve())
    except OSError:
        return str(p)


@lru_cache(maxsize=16)
def _load_jsonl_cached(cache_key: str) -> tuple[dict[str, Any], ...]:
    path = Path(cache_key)
    if not path.is_file():
        return ()
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return tuple(rows)


def load_jsonl(path: Path | str | None = None) -> list[dict[str, Any]]:
    key = _jsonl_cache_key(path)
    return list(_load_jsonl_cached(key))


def clear_jsonl_cache() -> None:
    """Drop cached JSONL reads after catalog/chunks/manifest writes in-process."""
    _load_jsonl_cached.cache_clear()
    from search_retrieval import invalidate_studied_episode_cache

    invalidate_studied_episode_cache()


def load_catalog() -> list[dict[str, Any]]:
    return load_jsonl(CATALOG_PATH)


def save_catalog(rows: list[dict[str, Any]]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    clear_jsonl_cache()


def catalog_by_number(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {r["episode_number"]: r for r in rows if r.get("episode_number") is not None}


def catalog_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rows}


def lookup_catalog_row(rows: list[dict[str, Any]], episode_id: str) -> dict[str, Any] | None:
    """Find catalog row by canonical id or episode number; None if missing."""
    for r in rows:
        if r["id"] == episode_id:
            return r
    from episode_ids import parse_numbered_episode_id

    num = parse_numbered_episode_id(episode_id)
    if num is not None:
        for r in rows:
            if r.get("episode_number") == num:
                return r
    return None


def resolve_catalog_row(rows: list[dict[str, Any]], episode_id: str) -> dict[str, Any]:
    """Find catalog row by canonical id or episode number."""
    row = lookup_catalog_row(rows, episode_id)
    if row is None:
        raise SystemExit(f"Episode not in catalog: {episode_id}")
    return row


def new_row(
    *,
    episode_number: int | None,
    title: str,
    slug: str,
    founders_url: str,
    published_at: str | None = None,
    colossus_url: str | None = None,
) -> dict[str, Any]:
    episode_id = make_id(episode_number, slug)
    return {
        "id": episode_id,
        "episode_number": episode_number,
        "title": title,
        "published_at": published_at,
        "founders_url": founders_url,
        "colossus_url": colossus_url,
        "slug": slug,
        "transcript_status": "pending",
        "transcript_path": None,
        "last_error": None,
        "fetched_at": None,
    }
