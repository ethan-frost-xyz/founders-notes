"""Vault episode tools — load_episode and list_episode_ids for the agent loop."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _setup_vault_paths() -> Path:
    from _bootstrap import resolve_vault_root, setup_ingestion_paths

    root = resolve_vault_root()
    setup_ingestion_paths(root)
    return root


def _content_paths(vault_root: Path):
    from paths import catalog_paths, expanded_file_path, notes_file_path, post_file_path

    cp = catalog_paths(vault_root)
    return cp.root, expanded_file_path, notes_file_path, post_file_path


def _load_catalog_rows(vault_root: Path) -> list[dict[str, Any]]:
    from catalog import load_jsonl
    from paths import catalog_paths

    return load_jsonl(catalog_paths(vault_root).episodes)


def _episode_listened(notes_path: Path) -> bool:
    if not notes_path.is_file():
        return False
    from markdown_io import has_timestamp_datapoints

    return has_timestamp_datapoints(notes_path)


def load_episode(episode_id: str, *, char_cap: int = 30_000) -> dict[str, Any]:
    """Load on-disk post / notes / expanded; expanded sections first when present."""
    vault_root = _setup_vault_paths()
    from catalog import lookup_catalog_row

    _, expanded_path_fn, notes_path_fn, post_path_fn = _content_paths(vault_root)

    rows = _load_catalog_rows(vault_root)
    row = lookup_catalog_row(rows, episode_id)
    if row is None:
        resolved = resolve_episode_ref(episode_id.strip())
        if resolved:
            row = lookup_catalog_row(rows, resolved)
    if row is None:
        candidates_result = list_episode_ids(episode_id.strip(), limit=5)
        return {
            "error": f"Episode not in catalog: {episode_id}",
            "candidates": candidates_result.get("episodes", []),
        }
    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")

    sections: dict[str, str] = {}
    order = [
        ("expanded", expanded_path_fn(ep_id, slug, num)),
        ("notes", notes_path_fn(ep_id, slug, num)),
        ("post", post_path_fn(ep_id, slug, num)),
    ]
    for key, path in order:
        rel = path.relative_to(vault_root) if path.is_absolute() else path
        full = vault_root / rel
        if full.is_file():
            sections[key] = full.read_text(encoding="utf-8")

    combined_order = ["expanded", "notes", "post"]
    remaining = char_cap
    trimmed: dict[str, str] = {}
    for key in combined_order:
        if key not in sections:
            continue
        text = sections[key]
        if len(text) <= remaining:
            trimmed[key] = text
            remaining -= len(text)
        else:
            trimmed[key] = text[:remaining]
            remaining = 0
            break

    notes_path = notes_path_fn(ep_id, slug, num)
    if not notes_path.is_absolute():
        notes_path = vault_root / notes_path

    return {
        "episode_id": ep_id,
        "sections": trimmed,
        "meta": {
            "listened": _episode_listened(notes_path),
            "has_expanded": "expanded" in trimmed,
            "has_post": "post" in trimmed,
            "title": row.get("title"),
        },
    }


def list_episode_ids(query: str, *, limit: int = 8) -> dict[str, Any]:
    """Match catalog by episode number, canonical id, or fuzzy title → ep-NNNN."""
    vault_root = _setup_vault_paths()

    rows = _load_catalog_rows(vault_root)
    token = query.strip()
    matches: list[tuple[float, dict[str, Any]]] = []

    from episode_ids import format_episode_id, parse_numbered_episode_id

    target_id: str | None = None
    if token.isdigit():
        try:
            target_id = format_episode_id(int(token))
        except ValueError:
            pass
    else:
        num = parse_numbered_episode_id(token)
        if num is not None:
            target_id = format_episode_id(num)

    if target_id:
        for row in rows:
            if row.get("id") == target_id:
                matches.append((1.0, row))
                break
    else:
        q = token.lower()
        q_tokens = [t for t in re.split(r"\W+", q) if len(t) >= 2]
        for row in rows:
            title = (row.get("title") or "").lower()
            ep_id = row.get("id", "")
            if q not in title and q not in ep_id.lower():
                if q_tokens and not any(t in title or t in ep_id.lower() for t in q_tokens):
                    continue
            score = SequenceMatcher(None, q, title).ratio()
            if q in title or q in ep_id.lower():
                score = max(score, 0.85)
            if score >= 0.45:
                matches.append((score, row))

    seen: set[str] = set()
    unique: list[tuple[float, dict[str, Any]]] = []
    for score, row in sorted(matches, key=lambda x: (-x[0], x[1].get("id", ""))):
        rid = row.get("id", "")
        if rid in seen:
            continue
        seen.add(rid)
        unique.append((score, row))

    from paths import notes_file_path

    episodes = []
    for score, row in unique[:limit]:
        ep_id = row["id"]
        slug = row.get("slug", "")
        num = row.get("episode_number")
        npath = notes_file_path(ep_id, slug, num)
        if not npath.is_absolute():
            npath = vault_root / npath
        episodes.append(
            {
                "episode_id": ep_id,
                "title": row.get("title"),
                "episode_number": row.get("episode_number"),
                "founders_url": row.get("founders_url"),
                "score": round(score, 3),
                "listened": _episode_listened(npath),
            }
        )
    return {"query": query, "episodes": episodes}


def resolve_episode_ref(ref: str) -> str | None:
    """Normalize a short ref to canonical ep-NNNN when unambiguous.

    Returns None when there are no matches or top fuzzy hits tie (e.g. Henry Ford).
    """
    _setup_vault_paths()
    result = list_episode_ids(ref, limit=3)
    eps = result.get("episodes") or []
    if not eps:
        return None
    top, *rest = eps
    top_score = top.get("score", 0)
    if top_score >= 1.0:
        return top["episode_id"]
    if top_score >= 0.85 and (not rest or rest[0].get("score", 0) < 0.85):
        return top["episode_id"]
    return None
