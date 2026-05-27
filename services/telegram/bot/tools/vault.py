"""Vault search tools — JSON-serializable evidence for the agent loop (SP1)."""

from __future__ import annotations

import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _vault_root() -> Path:
    env = os.environ.get("VAULT_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[4]


def _ensure_ingestion_path() -> Path:
    root = _vault_root()
    ingestion = root / "ingestion"
    lib = ingestion / "lib"
    for entry in (ingestion, lib):
        s = str(entry)
        if s not in sys.path:
            sys.path.insert(0, s)
    return root


def _paths():
    _ensure_ingestion_path()
    from paths import (
        CHUNKS_PATH,
        EMBEDDINGS_MANIFEST_PATH,
        EMBEDDINGS_PATH,
        ROOT,
        expanded_file_path,
        notes_file_path,
        post_file_path,
    )

    root = _vault_root()
    if root != ROOT:
        return (
            root / "catalog" / "chunks.jsonl",
            root / "catalog" / "embeddings.npy",
            root / "catalog" / "embeddings-manifest.jsonl",
            root,
            expanded_file_path,
            notes_file_path,
            post_file_path,
        )
    return (
        CHUNKS_PATH,
        EMBEDDINGS_PATH,
        EMBEDDINGS_MANIFEST_PATH,
        ROOT,
        expanded_file_path,
        notes_file_path,
        post_file_path,
    )


def search_vault_parent(query: str, k: int = 8) -> dict[str, Any]:
    _ensure_ingestion_path()
    from search_retrieval import search_parent_evidence

    chunks_path, embeddings_path, manifest_path, root, _, _, _ = _paths()
    return search_parent_evidence(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        root=root,
    )


def search_transcript(query: str, k: int = 8) -> dict[str, Any]:
    _ensure_ingestion_path()
    from search_retrieval import search_transcript_evidence

    chunks_path, _, _, root, _, _, _ = _paths()
    return search_transcript_evidence(query, k, chunks_path=chunks_path, root=root)


def _load_catalog_rows(vault_root: Path) -> list[dict[str, Any]]:
    from catalog import load_jsonl

    return load_jsonl(vault_root / "catalog" / "episodes.jsonl")


def _episode_listened(notes_path: Path) -> bool:
    if not notes_path.is_file():
        return False
    from markdown_io import has_timestamp_datapoints

    return has_timestamp_datapoints(notes_path)


def load_episode(episode_id: str, *, char_cap: int = 30_000) -> dict[str, Any]:
    """Load on-disk post / notes / expanded; expanded sections first when present."""
    vault_root = _ensure_ingestion_path()
    from catalog import resolve_catalog_row

    _, _, _, _, expanded_path_fn, notes_path_fn, post_path_fn = _paths()

    rows = _load_catalog_rows(vault_root)
    row = resolve_catalog_row(rows, episode_id)
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


_EPISODE_REF_RE = re.compile(
    r"(?:episode\s*)?(\d{1,4})\b|^(ep-(\d+))$",
    re.IGNORECASE,
)


def list_episode_ids(query: str, *, limit: int = 8) -> dict[str, Any]:
    """Fuzzy match catalog titles and numeric episode references → ep-NNNN."""
    vault_root = _ensure_ingestion_path()

    rows = _load_catalog_rows(vault_root)
    q = query.strip().lower()
    matches: list[tuple[float, dict[str, Any]]] = []

    from episode_ids import format_episode_id

    num_match = _EPISODE_REF_RE.search(q)
    if num_match:
        raw = num_match.group(1) or num_match.group(3)
        if raw:
            try:
                target = format_episode_id(int(raw))
                for row in rows:
                    if row.get("id") == target:
                        matches.append((1.0, row))
            except ValueError:
                pass

    for row in rows:
        title = (row.get("title") or "").lower()
        ep_id = row.get("id", "")
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
    """Normalize user ref to canonical ep-NNNN if found in catalog."""
    _ensure_ingestion_path()
    result = list_episode_ids(ref, limit=1)
    eps = result.get("episodes") or []
    return eps[0]["episode_id"] if eps else None
