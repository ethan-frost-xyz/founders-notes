"""Chunk index: load chunks.jsonl and split parent/transcript tiers (studied only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catalog import load_jsonl
from paths import CHUNKS_PATH, ROOT

from search_studied import studied_episode_ids

PARENT_SECTION_RE = re.compile(r"^(expanded|summary):")
TRANSCRIPT_SECTION_RE = re.compile(r"^transcript:")


def is_parent_chunk(ch: dict[str, Any]) -> bool:
    return bool(PARENT_SECTION_RE.match(ch.get("section", "")))


def is_transcript_chunk(ch: dict[str, Any]) -> bool:
    return bool(TRANSCRIPT_SECTION_RE.match(ch.get("section", "")))


def tier_boost(section: str) -> float:
    if section.startswith("expanded:"):
        return 0.2
    if section.startswith("summary:"):
        return 0.05
    return 0.0


def invalidate_chunk_index_cache() -> None:
    """Clear tier-list cache (tests, post-reindex hooks)."""
    _chunk_index_cache.clear()


def load_chunks(path: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl(path or CHUNKS_PATH)


@dataclass
class ChunkIndex:
    vault_root: Path
    chunks_path: Path
    all_chunks: list[dict[str, Any]]
    parent_chunks: list[dict[str, Any]]
    transcript_chunks: list[dict[str, Any]]
    by_chunk_id: dict[str, dict[str, Any]]
    cache_key: tuple[Any, ...]


_chunk_index_cache: dict[tuple[Any, ...], ChunkIndex] = {}


def _chunk_index_cache_key(chunks_path: Path, vault_root: Path) -> tuple[Any, ...]:
    mtime = chunks_path.stat().st_mtime if chunks_path.is_file() else 0.0
    return (str(chunks_path.resolve()), mtime, str(vault_root.resolve()))


def get_chunk_index(
    chunks_path: Path | None = None,
    *,
    root: Path | None = None,
) -> ChunkIndex:
    """Load chunks once and pre-split parent/transcript tiers (studied only)."""
    vault_root = (root or ROOT).resolve()
    cpath = chunks_path or CHUNKS_PATH
    key = _chunk_index_cache_key(cpath, vault_root)
    cached = _chunk_index_cache.get(key)
    if cached is not None:
        return cached

    all_chunks = load_chunks(cpath)
    studied = studied_episode_ids(root=vault_root)
    parent_chunks: list[dict[str, Any]] = []
    transcript_chunks: list[dict[str, Any]] = []
    by_chunk_id: dict[str, dict[str, Any]] = {}
    for ch in all_chunks:
        cid = ch.get("chunk_id")
        if cid:
            by_chunk_id[str(cid)] = ch
        ep = ch.get("id") or ch.get("episode_id")
        if not ep or str(ep) not in studied:
            continue
        if is_parent_chunk(ch):
            parent_chunks.append(ch)
        elif is_transcript_chunk(ch):
            transcript_chunks.append(ch)

    index = ChunkIndex(
        vault_root=vault_root,
        chunks_path=cpath,
        all_chunks=all_chunks,
        parent_chunks=parent_chunks,
        transcript_chunks=transcript_chunks,
        by_chunk_id=by_chunk_id,
        cache_key=key,
    )
    _chunk_index_cache[key] = index
    return index
