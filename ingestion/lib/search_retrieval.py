"""Hybrid retrieval over catalog/chunks.jsonl — facade + evidence wrappers.

Implementation modules: search_studied, search_chunk_index, search_embeddings,
search_hybrid, search_cache.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from search_chunk_index import (
    ChunkIndex,
    get_chunk_index,
    invalidate_chunk_index_cache,
    is_parent_chunk,
    is_transcript_chunk,
    load_chunks,
    tier_boost,
)
from search_embeddings import (
    chunk_content_hash,
    embed_queries,
    embed_query,
    excerpt_hash,
    get_embedding_store,
    load_embeddings_manifest,
    load_embeddings_matrix,
    structured_embed_text,
)
from search_hybrid import (
    DEFAULT_EXCERPT_CHARS,
    RRF_K,
    chunk_to_hit,
    hybrid_search_parent,
    hybrid_search_parent_chunks,
    load_chunk_source_excerpt,
    merge_rrf_chunk_lists,
    search_chunks_keyword,
    search_transcript_keyword,
)
from search_studied import (
    episode_is_studied,
    invalidate_studied_episode_cache,
    is_studied_chunk,
    studied_episode_ids,
)

LOAD_EPISODE_CHAR_CAP = 30_000

__all__ = [
    "DEFAULT_EXCERPT_CHARS",
    "ChunkIndex",
    "LOAD_EPISODE_CHAR_CAP",
    "RRF_K",
    "chunk_content_hash",
    "chunk_to_hit",
    "chunks_needing_embedding",
    "embed_queries",
    "embed_query",
    "episode_is_studied",
    "excerpt_hash",
    "get_chunk_index",
    "get_embedding_store",
    "hybrid_search_parent",
    "hybrid_search_parent_chunks",
    "invalidate_chunk_index_cache",
    "invalidate_studied_episode_cache",
    "is_parent_chunk",
    "is_studied_chunk",
    "is_transcript_chunk",
    "load_chunk_source_excerpt",
    "load_chunks",
    "load_embeddings_manifest",
    "load_embeddings_matrix",
    "merge_rrf_chunk_lists",
    "parent_chunks_for_embedding",
    "search_chunks_keyword",
    "search_parent_evidence",
    "search_transcript_evidence",
    "search_transcript_keyword",
    "structured_embed_text",
    "studied_episode_ids",
    "tier_boost",
]


def search_parent_evidence(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    root: Path | None = None,
    query_vector: np.ndarray | None = None,
    index: ChunkIndex | None = None,
) -> dict[str, Any]:
    result = hybrid_search_parent(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        root=root,
        query_vector=query_vector,
        index=index,
    )
    result["meta"]["retrieval_meta"] = dict(result["meta"])
    return result


def search_transcript_evidence(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    root: Path | None = None,
    index: ChunkIndex | None = None,
) -> dict[str, Any]:
    from paths import ROOT

    vault_root = root or ROOT
    hits = search_transcript_keyword(
        query,
        k,
        chunks_path=chunks_path,
        root=vault_root,
        index=index,
    )
    return {
        "hits": [chunk_to_hit(ch, root=vault_root) for ch in hits],
        "meta": {
            "query": query,
            "tier": "transcript",
            "k": k,
            "studied_filter_applied": True,
        },
    }


def parent_chunks_for_embedding(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [ch for ch in chunks if is_parent_chunk(ch) and ch.get("chunk_id")]


def chunks_needing_embedding(
    parent_chunks: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parent chunks with new or changed content vs manifest."""
    known = {row["chunk_id"]: row.get("content_hash") for row in manifest if row.get("chunk_id")}
    out: list[dict[str, Any]] = []
    for ch in parent_chunks:
        cid = ch.get("chunk_id")
        if not cid:
            continue
        h = chunk_content_hash(ch)
        if known.get(cid) != h:
            out.append(ch)
    return out
