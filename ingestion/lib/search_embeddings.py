"""Embedding store, query embed API, and structured embed text per chunk."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from catalog import load_jsonl
from paths import EMBEDDINGS_MANIFEST_PATH, EMBEDDINGS_PATH

_EXPANDED_FIELD_RE = re.compile(
    r"^(Context|Quote|Key takeaway):\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def load_embeddings_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl(path or EMBEDDINGS_MANIFEST_PATH)


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
