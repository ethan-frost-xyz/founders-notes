"""Keyword + vector hybrid search and transcript keyword search."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import numpy as np

from paths import ROOT

from search_chunk_index import (
    ChunkIndex,
    get_chunk_index,
    is_parent_chunk,
    load_chunks,
    tier_boost,
)
from search_embeddings import embed_query, get_embedding_store
from search_studied import is_studied_chunk

RRF_K = 60
DEFAULT_EXCERPT_CHARS = 800


def load_chunk_source_excerpt(
    ch: dict[str, Any],
    *,
    max_chars: int = DEFAULT_EXCERPT_CHARS,
    root: Path | None = None,
) -> str:
    """Read source file around chunk start_line; fall back to stored excerpt."""
    stored = (ch.get("excerpt") or "").strip()
    rel = ch.get("source_path")
    if not rel:
        return stored[:max_chars]
    path = (root or ROOT) / rel
    if not path.is_file():
        return stored[:max_chars]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return stored[:max_chars]
    start = int(ch.get("start_line") or 1)
    idx = max(0, start - 1)
    window = lines[idx : idx + 40]
    text = "\n".join(window).strip() or stored
    return text[:max_chars]


def chunk_to_hit(ch: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    stored = (ch.get("excerpt") or "").strip()
    excerpt = stored or load_chunk_source_excerpt(ch, root=root)
    hit: dict[str, Any] = {
        "chunk_id": ch.get("chunk_id", ""),
        "episode_id": ch.get("id", ""),
        "section": ch.get("section", ""),
        "source_path": ch.get("source_path", ""),
        "start_line": ch.get("start_line"),
        "excerpt": excerpt,
    }
    if ch.get("title"):
        hit["title"] = ch["title"]
    if ch.get("founders_url"):
        hit["founders_url"] = ch["founders_url"]
    return hit


def _keyword_query_terms(query: str) -> list[str]:
    """Split multi-word queries into terms; single-token queries stay literal."""
    terms = [t for t in re.split(r"\W+", query.strip()) if len(t) >= 3]
    if len(terms) >= 2:
        return terms
    q = query.strip()
    return [q] if q else []


def search_chunks_keyword(
    query: str,
    limit: int,
    *,
    chunks: list[dict[str, Any]] | None = None,
    chunk_predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    """Keyword match on chunk excerpts; multi-word queries score by term overlap."""
    filt = chunk_predicate
    terms = _keyword_query_terms(query)
    if not terms:
        return []

    rows = chunks if chunks is not None else load_chunks()
    hits: list[tuple[float, dict[str, Any]]] = []
    if len(terms) == 1:
        pattern = re.compile(re.escape(terms[0]), re.IGNORECASE)
        for ch in rows:
            if filt and not filt(ch):
                continue
            excerpt = ch.get("excerpt") or ""
            if not pattern.search(excerpt):
                continue
            score = float(len(pattern.findall(excerpt)))
            hits.append((score, ch))
    else:
        lowered = [t.lower() for t in terms]
        for ch in rows:
            if filt and not filt(ch):
                continue
            excerpt = (ch.get("excerpt") or "").lower()
            if not excerpt:
                continue
            matched = sum(1 for t in lowered if t in excerpt)
            if matched == 0:
                continue
            score = float(matched)
            if all(t in excerpt for t in lowered):
                score += float(len(lowered))
            hits.append((score, ch))

    hits.sort(key=lambda x: (-x[0], x[1].get("id", ""), x[1].get("start_line", 0)))
    return hits[:limit]


def _rrf_scores(ranked_lists: list[list[str]], *, rrf_k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


def _vector_rank_parent(
    query: str,
    limit: int,
    *,
    parent_chunks: list[dict[str, Any]] | None = None,
    chunks: list[dict[str, Any]] | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    query_vector: np.ndarray | None = None,
    root: Path | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    store = get_embedding_store(embeddings_path=embeddings_path, manifest_path=manifest_path)
    matrix = store.matrix
    manifest = store.manifest
    if matrix is None or not manifest:
        return []

    if parent_chunks is not None:
        parent_by_id = {
            str(ch["chunk_id"]): ch for ch in parent_chunks if ch.get("chunk_id")
        }
    else:
        vault_root = root or ROOT
        rows = chunks if chunks is not None else load_chunks()
        parent_by_id = {
            str(ch["chunk_id"]): ch
            for ch in rows
            if ch.get("chunk_id")
            and is_parent_chunk(ch)
            and is_studied_chunk(ch, root=vault_root)
        }

    scored: list[tuple[float, dict[str, Any]]] = []
    if query_vector is None:
        query_vector = embed_query(query)
    if query_vector is None:
        return []

    q = query_vector.astype(np.float64)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []
    q = q / q_norm

    for row in manifest:
        cid = row.get("chunk_id")
        idx = row.get("index")
        if cid is None or idx is None:
            continue
        ch = parent_by_id.get(str(cid))
        if ch is None:
            continue
        vec = matrix[int(idx)].astype(np.float64)
        v_norm = np.linalg.norm(vec)
        if v_norm == 0:
            continue
        sim = float(np.dot(q, vec / v_norm))
        scored.append((sim, ch))

    scored.sort(key=lambda x: (-x[0], x[1].get("chunk_id", "")))
    return scored[:limit]


def _parent_search_predicate(ch: dict[str, Any], *, root: Path | None) -> bool:
    return is_parent_chunk(ch) and is_studied_chunk(ch, root=root)


def merge_rrf_chunk_lists(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    cap: int,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Union variant result lists; dedupe by chunk_id with aggregated RRF."""
    id_lists: list[list[str]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for chunk_list in ranked_lists:
        ids: list[str] = []
        for ch in chunk_list:
            cid = ch.get("chunk_id")
            if not cid or not _parent_search_predicate(ch, root=root):
                continue
            by_id[cid] = ch
            ids.append(cid)
        if ids:
            id_lists.append(ids)
    if not id_lists:
        return []
    rrf = _rrf_scores(id_lists)
    ordered = sorted(
        rrf.keys(),
        key=lambda cid: (-(rrf[cid] + tier_boost(by_id[cid].get("section", ""))), cid),
    )
    return [by_id[cid] for cid in ordered[:cap] if cid in by_id]


def hybrid_search_parent_chunks(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    query_vector: np.ndarray | None = None,
    root: Path | None = None,
    index: ChunkIndex | None = None,
) -> list[dict[str, Any]]:
    """RRF merge of keyword + cosine ranks over expanded + summary tiers (studied only)."""
    vault_root = root or ROOT
    if index is None:
        index = get_chunk_index(chunks_path=chunks_path, root=vault_root)
    parent_chunks = index.parent_chunks
    pool = max(k * 4, 32)

    kw_hits = search_chunks_keyword(query, pool, chunks=parent_chunks)
    kw_ranked = [ch["chunk_id"] for _, ch in kw_hits if ch.get("chunk_id")]

    vec_hits = _vector_rank_parent(
        query,
        pool,
        parent_chunks=parent_chunks,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        query_vector=query_vector,
        root=vault_root,
    )
    vec_ranked = [ch["chunk_id"] for _, ch in vec_hits if ch.get("chunk_id")]

    lists = [r for r in (kw_ranked, vec_ranked) if r]
    if not lists:
        return []

    rrf = _rrf_scores(lists)
    by_id = {ch["chunk_id"]: ch for ch in parent_chunks if ch.get("chunk_id")}

    ordered = sorted(
        rrf.keys(),
        key=lambda cid: (
            -(rrf[cid] + tier_boost(by_id[cid].get("section", ""))),
            cid,
        ),
    )
    return [by_id[cid] for cid in ordered[:k] if cid in by_id]


def hybrid_search_parent(
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
    vault_root = root or ROOT
    store = get_embedding_store(embeddings_path=embeddings_path, manifest_path=manifest_path)
    if index is None:
        index = get_chunk_index(chunks_path=chunks_path, root=vault_root)
    hits = hybrid_search_parent_chunks(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        query_vector=query_vector,
        root=vault_root,
        index=index,
    )
    return {
        "hits": [chunk_to_hit(ch, root=vault_root) for ch in hits],
        "meta": {
            "query": query,
            "tier": "parent",
            "k": k,
            "embed_present": store.matrix is not None and bool(store.manifest),
            "tiers_searched": ["expanded", "summary"],
            "candidate_count": len(hits),
            "studied_filter_applied": True,
        },
    }


def search_transcript_keyword(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    root: Path | None = None,
    index: ChunkIndex | None = None,
) -> list[dict[str, Any]]:
    vault_root = root or ROOT
    if index is None:
        index = get_chunk_index(chunks_path=chunks_path, root=vault_root)
    hits = search_chunks_keyword(query, k, chunks=index.transcript_chunks)
    return [ch for _, ch in hits]
