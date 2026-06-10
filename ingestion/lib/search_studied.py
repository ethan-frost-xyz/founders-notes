"""Studied-episode detection (timestamp bullets in notes)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from catalog import load_jsonl
from markdown_io import has_timestamp_datapoints
from paths import ROOT, content_filename, folder_name

_studied_state: dict[str, tuple[tuple[Any, ...], set[str]]] = {}


def invalidate_studied_episode_cache() -> None:
    """Clear studied-id cache (tests, post-reindex hooks)."""
    _studied_state.clear()
    from search_chunk_index import invalidate_chunk_index_cache

    invalidate_chunk_index_cache()


def _tree_max_mtime(directory: Path, glob_pattern: str) -> float:
    if not directory.is_dir():
        return 0.0
    latest = 0.0
    for path in directory.glob(glob_pattern):
        if not path.is_file():
            continue
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def _studied_ids_cache_key(vault_root: Path) -> tuple[Any, ...]:
    catalog = vault_root / "catalog" / "episodes.jsonl"
    chunks = vault_root / "catalog" / "chunks.jsonl"
    notes_dir = vault_root / "content" / "notes"
    parts: list[Any] = [str(vault_root.resolve())]
    for path in (catalog, chunks):
        parts.append(path.stat().st_mtime if path.is_file() else 0.0)
    parts.append(_tree_max_mtime(notes_dir, "**/*.notes.md"))
    return tuple(parts)


def _notes_path_for_root(
    vault_root: Path,
    episode_id: str,
    slug: str,
    episode_number: int | None,
) -> Path:
    folder = folder_name(episode_id, slug, episode_number)
    return vault_root / "content" / "notes" / folder / content_filename(folder, "notes")


def _refresh_studied_ids(vault_root: Path) -> set[str]:
    """Rebuild studied-id set when cache key changes (notes/catalog/chunks mtime)."""
    rk = str(vault_root.resolve())
    cache_key = _studied_ids_cache_key(vault_root)
    state = _studied_state.get(rk)
    if state is not None and state[0] == cache_key:
        return state[1]
    catalog_path = vault_root / "catalog" / "episodes.jsonl"
    rows = load_jsonl(catalog_path) if catalog_path.is_file() else []
    ids: set[str] = set()
    for row in rows:
        ep_id = row["id"]
        npath = _notes_path_for_root(vault_root, ep_id, row["slug"], row.get("episode_number"))
        if npath.is_file() and has_timestamp_datapoints(npath):
            ids.add(ep_id)
    _studied_state[rk] = (cache_key, ids)
    return ids


def studied_episode_ids(*, root: Path | None = None) -> set[str]:
    """Episode ids with timestamp bullets in notes (studied corpus)."""
    return _refresh_studied_ids((root or ROOT).resolve())


def episode_is_studied(episode_id: str, *, root: Path | None = None) -> bool:
    vault_root = (root or ROOT).resolve()
    rk = str(vault_root)
    state = _studied_state.get(rk)
    if state is None:
        return episode_id in studied_episode_ids(root=vault_root)
    return episode_id in state[1]


def is_studied_chunk(ch: dict[str, Any], *, root: Path | None = None) -> bool:
    ep = ch.get("id") or ch.get("episode_id")
    return bool(ep) and episode_is_studied(str(ep), root=root)
