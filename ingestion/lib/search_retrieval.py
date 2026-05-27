"""Hybrid retrieval over catalog/chunks.jsonl (parent + transcript tiers)."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np

from catalog import load_jsonl
from paths import (
    CHUNKS_PATH,
    EMBEDDINGS_MANIFEST_PATH,
    EMBEDDINGS_PATH,
    ROOT,
    expanded_file_path,
    notes_file_path,
    post_file_path,
)

PARENT_SECTION_RE = re.compile(r"^(post|notes|expanded):")
TRANSCRIPT_SECTION_RE = re.compile(r"^transcript:")
RRF_K = 60
DEFAULT_EXCERPT_CHARS = 800
LOAD_EPISODE_CHAR_CAP = 30_000


def is_parent_chunk(ch: dict[str, Any]) -> bool:
    return bool(PARENT_SECTION_RE.match(ch.get("section", "")))


def is_transcript_chunk(ch: dict[str, Any]) -> bool:
    return bool(TRANSCRIPT_SECTION_RE.match(ch.get("section", "")))


def tier_boost(section: str) -> float:
    if section.startswith("expanded:"):
        return 0.2
    if section.startswith("notes:"):
        return 0.1
    return 0.0


def excerpt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def chunk_content_hash(ch: dict[str, Any]) -> str:
    key = "|".join(
        (
            str(ch.get("chunk_id", "")),
            str(ch.get("excerpt", "")),
            str(ch.get("char_count", "")),
        )
    )
    return excerpt_hash(key)


def load_chunks(path: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl(path or CHUNKS_PATH)


def load_embeddings_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl(path or EMBEDDINGS_MANIFEST_PATH)


def load_embeddings_matrix(path: Path | None = None) -> np.ndarray | None:
    p = path or EMBEDDINGS_PATH
    if not p.exists():
        return None
    return np.load(p)


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
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    """Keyword match on chunk excerpts; multi-word queries score by term overlap."""
    filt = chunk_predicate or predicate
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
    chunks: list[dict[str, Any]],
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    query_vector: np.ndarray | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    matrix = load_embeddings_matrix(embeddings_path)
    manifest = load_embeddings_manifest(manifest_path)
    if matrix is None or not manifest:
        return []

    by_id = {ch["chunk_id"]: ch for ch in chunks if ch.get("chunk_id")}
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
        if cid is None or idx is None or cid not in by_id:
            continue
        if not is_parent_chunk(by_id[cid]):
            continue
        vec = matrix[int(idx)].astype(np.float64)
        v_norm = np.linalg.norm(vec)
        if v_norm == 0:
            continue
        sim = float(np.dot(q, vec / v_norm))
        scored.append((sim, by_id[cid]))

    scored.sort(key=lambda x: (-x[0], x[1].get("chunk_id", "")))
    return scored[:limit]


def embed_query(query: str) -> np.ndarray | None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("OPENROUTER_EMBED_MODEL", "").strip()
    if not api_key or not model:
        return None
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
    )
    resp = client.embeddings.create(model=model, input=[query])
    return np.array(resp.data[0].embedding, dtype=np.float32)


def _hybrid_search_parent_chunks(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    query_vector: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """RRF merge of keyword + cosine ranks; tier boost on expanded > notes > post."""
    chunks = load_chunks(chunks_path)
    parent_chunks = [ch for ch in chunks if is_parent_chunk(ch)]
    pool = max(k * 3, 24)

    kw_hits = search_chunks_keyword(
        query, pool, chunks=parent_chunks, chunk_predicate=is_parent_chunk
    )
    kw_ranked = [ch["chunk_id"] for _, ch in kw_hits if ch.get("chunk_id")]

    vec_hits = _vector_rank_parent(
        query,
        pool,
        chunks=chunks,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        query_vector=query_vector,
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
) -> dict[str, Any]:
    hits = _hybrid_search_parent_chunks(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        query_vector=query_vector,
    )
    return {
        "hits": [chunk_to_hit(ch, root=root) for ch in hits],
        "meta": {"query": query, "tier": "parent", "k": k},
    }


def search_transcript_keyword(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
) -> list[dict[str, Any]]:
    chunks = load_chunks(chunks_path)
    hits = search_chunks_keyword(
        query,
        k,
        chunks=chunks,
        chunk_predicate=is_transcript_chunk,
    )
    return [ch for _, ch in hits]


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


def search_parent_evidence(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    root: Path | None = None,
    query_vector: np.ndarray | None = None,
) -> dict[str, Any]:
    return hybrid_search_parent(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        root=root,
        query_vector=query_vector,
    )


def search_transcript_evidence(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    hits = search_transcript_keyword(query, k, chunks_path=chunks_path)
    return {
        "hits": [chunk_to_hit(ch, root=root) for ch in hits],
        "meta": {"query": query, "tier": "transcript", "k": k},
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
