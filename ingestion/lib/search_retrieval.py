"""Hybrid retrieval over catalog/chunks.jsonl (parent + transcript tiers)."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np

from catalog import load_jsonl
from markdown_io import has_timestamp_datapoints
from paths import (
    CHUNKS_PATH,
    EMBEDDINGS_MANIFEST_PATH,
    EMBEDDINGS_PATH,
    ROOT,
    content_filename,
    folder_name,
)

PARENT_SECTION_RE = re.compile(r"^(expanded|summary):")
TRANSCRIPT_SECTION_RE = re.compile(r"^transcript:")
RRF_K = 60
DEFAULT_EXCERPT_CHARS = 800
LOAD_EPISODE_CHAR_CAP = 30_000
_EXPANDED_FIELD_RE = re.compile(
    r"^(Context|Quote|Key takeaway):\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)

_studied_episode_ids: set[str] | None = None
_studied_cache_key: tuple[Any, ...] | None = None


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


def invalidate_studied_episode_cache() -> None:
    """Clear studied-id cache (tests, post-reindex hooks)."""
    global _studied_episode_ids, _studied_cache_key
    _studied_episode_ids = None
    _studied_cache_key = None


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


def studied_episode_ids(*, root: Path | None = None) -> set[str]:
    """Episode ids with timestamp bullets in notes (studied corpus)."""
    global _studied_episode_ids, _studied_cache_key
    vault_root = (root or ROOT).resolve()
    cache_key = _studied_ids_cache_key(vault_root)
    if _studied_episode_ids is not None and _studied_cache_key == cache_key:
        return _studied_episode_ids
    catalog_path = vault_root / "catalog" / "episodes.jsonl"
    rows = load_jsonl(catalog_path) if catalog_path.is_file() else []
    ids: set[str] = set()
    for row in rows:
        ep_id = row["id"]
        npath = _notes_path_for_root(vault_root, ep_id, row["slug"], row.get("episode_number"))
        if npath.is_file() and has_timestamp_datapoints(npath):
            ids.add(ep_id)
    _studied_episode_ids = ids
    _studied_cache_key = cache_key
    return ids


def episode_is_studied(episode_id: str, *, root: Path | None = None) -> bool:
    return episode_id in studied_episode_ids(root=root)


def is_studied_chunk(ch: dict[str, Any], *, root: Path | None = None) -> bool:
    ep = ch.get("id") or ch.get("episode_id")
    return bool(ep) and episode_is_studied(str(ep), root=root)


def structured_embed_text(ch: dict[str, Any]) -> str:
    """Retrieval-optimized embed input per chunk type."""
    section = ch.get("section") or ""
    title = ch.get("title") or ""
    ep_id = ch.get("id") or ""
    ep_num = ch.get("episode_number")
    pub = ch.get("published_at") or ""
    if section.startswith("summary:"):
        header = f"Episode: {title} ({ep_id}"
        if ep_num is not None:
            header += f", ep-{int(ep_num):04d}"
        header += ")"
        return f"{header}\n{ch.get('excerpt') or ''}"

    excerpt = ch.get("excerpt") or ""
    ts = ""
    first = excerpt.splitlines()[0] if excerpt else ""
    if first.startswith("###"):
        ts = first.lstrip("#").strip()
    fields: dict[str, str] = {}
    for match in _EXPANDED_FIELD_RE.finditer(excerpt):
        fields[match.group(1).lower()] = match.group(2).strip()
    lines = [
        f"Episode: {title} ({ep_id}",
    ]
    if ep_num is not None:
        lines[0] += f", ep-{int(ep_num):04d}"
    if pub:
        lines[0] += f", {pub}"
    lines[0] += ")"
    if ts:
        lines.append(f"Timestamp: {ts}")
    if fields.get("context"):
        lines.append(f"Context: {fields['context']}")
    if fields.get("quote"):
        lines.append(f"Quote: {fields['quote']}")
    takeaway = fields.get("key takeaway") or fields.get("key_takeaway")
    if takeaway:
        lines.append(f"Takeaway: {takeaway}")
    if len(lines) == 1:
        lines.append(excerpt[:8000])
    return "\n".join(lines)


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


@dataclass
class _EmbeddingStore:
    matrix: np.ndarray | None
    manifest: list[dict[str, Any]]
    matrix_mtime: float
    manifest_mtime: float


_embedding_store: _EmbeddingStore | None = None


def _embedding_file_mtimes(
    embeddings_path: Path,
    manifest_path: Path,
) -> tuple[float, float]:
    m_emb = embeddings_path.stat().st_mtime if embeddings_path.is_file() else 0.0
    m_man = manifest_path.stat().st_mtime if manifest_path.is_file() else 0.0
    return m_emb, m_man


def get_embedding_store(
    *,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
) -> _EmbeddingStore:
    """Load embeddings matrix + manifest once per process; invalidate on mtime change."""
    global _embedding_store
    emb_path = embeddings_path or EMBEDDINGS_PATH
    man_path = manifest_path or EMBEDDINGS_MANIFEST_PATH
    m_emb, m_man = _embedding_file_mtimes(emb_path, man_path)
    if (
        _embedding_store is not None
        and _embedding_store.matrix_mtime == m_emb
        and _embedding_store.manifest_mtime == m_man
    ):
        return _embedding_store
    matrix = np.load(emb_path) if emb_path.is_file() else None
    manifest = load_embeddings_manifest(man_path) if man_path.is_file() else []
    _embedding_store = _EmbeddingStore(
        matrix=matrix,
        manifest=manifest,
        matrix_mtime=m_emb,
        manifest_mtime=m_man,
    )
    return _embedding_store


def load_embeddings_matrix(path: Path | None = None) -> np.ndarray | None:
    store = get_embedding_store(embeddings_path=path)
    return store.matrix


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
    root: Path | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    store = get_embedding_store(embeddings_path=embeddings_path, manifest_path=manifest_path)
    matrix = store.matrix
    manifest = store.manifest
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
        ch = by_id[cid]
        if not is_parent_chunk(ch) or not is_studied_chunk(ch, root=root):
            continue
        vec = matrix[int(idx)].astype(np.float64)
        v_norm = np.linalg.norm(vec)
        if v_norm == 0:
            continue
        sim = float(np.dot(q, vec / v_norm))
        scored.append((sim, by_id[cid]))

    scored.sort(key=lambda x: (-x[0], x[1].get("chunk_id", "")))
    return scored[:limit]


def _embed_api_config() -> tuple[str, str, str] | None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("OPENROUTER_EMBED_MODEL", "").strip()
    if not api_key or not model:
        return None
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    return api_key, model, base_url


def embed_queries(queries: list[str]) -> list[np.ndarray | None]:
    """Batch-embed multiple query strings in one API call."""
    if not queries:
        return []
    cfg = _embed_api_config()
    if cfg is None:
        return [None] * len(queries)
    api_key, model, base_url = cfg
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=queries)
    by_index = {item.index: item.embedding for item in resp.data}
    out: list[np.ndarray | None] = []
    for i in range(len(queries)):
        vec = by_index.get(i)
        out.append(np.array(vec, dtype=np.float32) if vec is not None else None)
    return out


@lru_cache(maxsize=128)
def _embed_query_cached(query: str) -> tuple[float, ...] | None:
    vecs = embed_queries([query])
    if not vecs or vecs[0] is None:
        return None
    return tuple(float(x) for x in vecs[0].tolist())


def embed_query(query: str) -> np.ndarray | None:
    cached = _embed_query_cached(query.strip())
    if cached is None:
        return None
    return np.array(cached, dtype=np.float32)


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


def _hybrid_search_parent_chunks(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    query_vector: np.ndarray | None = None,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """RRF merge of keyword + cosine ranks over expanded + summary tiers (studied only)."""
    vault_root = root or ROOT
    chunks = load_chunks(chunks_path)
    parent_chunks = [
        ch for ch in chunks if _parent_search_predicate(ch, root=vault_root)
    ]
    pool = max(k * 4, 32)

    def parent_pred(ch: dict[str, Any]) -> bool:
        return _parent_search_predicate(ch, root=vault_root)

    kw_hits = search_chunks_keyword(query, pool, chunks=parent_chunks, chunk_predicate=parent_pred)
    kw_ranked = [ch["chunk_id"] for _, ch in kw_hits if ch.get("chunk_id")]

    vec_hits = _vector_rank_parent(
        query,
        pool,
        chunks=chunks,
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
) -> dict[str, Any]:
    vault_root = root or ROOT
    store = get_embedding_store(embeddings_path=embeddings_path, manifest_path=manifest_path)
    hits = _hybrid_search_parent_chunks(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        query_vector=query_vector,
        root=vault_root,
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
) -> list[dict[str, Any]]:
    vault_root = root or ROOT
    chunks = load_chunks(chunks_path)

    def transcript_pred(ch: dict[str, Any]) -> bool:
        return is_transcript_chunk(ch) and is_studied_chunk(ch, root=vault_root)

    hits = search_chunks_keyword(
        query,
        k,
        chunks=chunks,
        chunk_predicate=transcript_pred,
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
    result = hybrid_search_parent(
        query,
        k,
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
        root=root,
        query_vector=query_vector,
    )
    result["meta"]["retrieval_meta"] = dict(result["meta"])
    return result


def search_transcript_evidence(
    query: str,
    k: int = 8,
    *,
    chunks_path: Path | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    vault_root = root or ROOT
    hits = search_transcript_keyword(query, k, chunks_path=chunks_path, root=vault_root)
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
