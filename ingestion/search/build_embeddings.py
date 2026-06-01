#!/usr/bin/env python3
"""Build parent-tier embedding index (catalog/embeddings.npy + manifest)."""

from __future__ import annotations

import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import json
import os
from typing import Any

import numpy as np
from dotenv import load_dotenv

from paths import (
    CHUNKS_PATH,
    EMBEDDINGS_MANIFEST_PATH,
    EMBEDDINGS_META_PATH,
    EMBEDDINGS_PATH,
    ROOT,
)
from search_retrieval import (
    chunk_content_hash,
    load_chunks,
    load_embeddings_manifest,
    parent_chunks_for_embedding,
)

load_dotenv(ROOT / ".env")


def embed_texts(texts: list[str], *, model: str, api_key: str, base_url: str | None) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=(base_url or "https://openrouter.ai/api/v1").rstrip("/"),
    )
    resp = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in resp.data]


def _load_embeddings_meta(meta_path: Path) -> dict[str, Any]:
    if not meta_path.is_file():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_embeddings_meta(meta_path: Path, *, embed_model: str, dim: int) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps({"embed_model": embed_model, "dim": dim}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _probe_embedding_dim(
    *, model: str, api_key: str, base_url: str | None
) -> int | None:
    embs = embed_texts(["."], model=model, api_key=api_key, base_url=base_url)
    if not embs:
        return None
    return len(embs[0])


def _cache_invalidation_reason(
    *,
    meta: dict[str, Any],
    old_matrix: np.ndarray | None,
    old_manifest: list[dict[str, Any]],
    embed_model: str,
    api_key: str,
    apply: bool,
    base_url: str | None,
) -> str | None:
    if old_matrix is None or not old_manifest:
        return None

    stored_model = meta.get("embed_model")
    if isinstance(stored_model, str) and stored_model.strip():
        if embed_model and stored_model.strip() != embed_model:
            return "embed_model_changed"

    stored_dim = meta.get("dim")
    if stored_dim is not None:
        try:
            if int(stored_dim) != int(old_matrix.shape[1]):
                return "dim_mismatch_meta"
        except (TypeError, ValueError):
            pass

    if len(old_manifest) != int(old_matrix.shape[0]):
        return "manifest_row_count_mismatch"

    if not meta and apply and embed_model and api_key:
        probe_dim = _probe_embedding_dim(model=embed_model, api_key=api_key, base_url=base_url)
        if probe_dim is not None and probe_dim != int(old_matrix.shape[1]):
            return "legacy_dim_probe_mismatch"

    return None


def _rows_have_uniform_dim(rows: list[np.ndarray]) -> bool:
    if not rows:
        return True
    dim = rows[0].shape[0]
    return all(r.shape[0] == dim for r in rows)


def build_parent_embeddings(
    *,
    apply: bool = True,
    batch_size: int = 32,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    meta_path: Path | None = None,
    force_full_rebuild: bool = False,
) -> dict[str, Any]:
    """Incremental parent-only vectors aligned to manifest row index."""
    chunks_path = chunks_path or CHUNKS_PATH
    embeddings_path = embeddings_path or EMBEDDINGS_PATH
    manifest_path = manifest_path or EMBEDDINGS_MANIFEST_PATH
    meta_path = meta_path or EMBEDDINGS_META_PATH

    parent = parent_chunks_for_embedding(load_chunks(chunks_path))
    old_manifest = load_embeddings_manifest(manifest_path)
    old_by_id = {row["chunk_id"]: row for row in old_manifest if row.get("chunk_id")}

    old_matrix = None
    if embeddings_path.exists() and old_manifest and not force_full_rebuild:
        old_matrix = np.load(embeddings_path)

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("OPENROUTER_EMBED_MODEL", "").strip()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or None

    invalidated_cache = False
    invalidated_reason: str | None = None
    if force_full_rebuild:
        invalidated_cache = True
        invalidated_reason = "force_full_rebuild"
        old_manifest = []
        old_matrix = None
    elif old_matrix is not None:
        meta = _load_embeddings_meta(meta_path)
        invalidated_reason = _cache_invalidation_reason(
            meta=meta,
            old_matrix=old_matrix,
            old_manifest=old_manifest,
            embed_model=model,
            api_key=api_key,
            apply=apply,
            base_url=base_url,
        )
        if invalidated_reason:
            invalidated_cache = True
            old_manifest = []
            old_matrix = None

    vectors: dict[str, np.ndarray] = {}
    for row in old_manifest:
        cid = row.get("chunk_id")
        idx = row.get("index")
        if cid is None or idx is None or old_matrix is None:
            continue
        ch = next((c for c in parent if c.get("chunk_id") == cid), None)
        if ch and old_by_id.get(cid, {}).get("content_hash") == chunk_content_hash(ch):
            vectors[cid] = old_matrix[int(idx)]

    to_embed = [ch for ch in parent if ch.get("chunk_id") not in vectors]
    embedded_new = 0

    if to_embed and apply:
        if not api_key or not model:
            raise SystemExit("Set OPENROUTER_API_KEY and OPENROUTER_EMBED_MODEL for --apply")
        for i in range(0, len(to_embed), batch_size):
            batch = to_embed[i : i + batch_size]
            texts = [(ch.get("excerpt") or ch.get("chunk_id", ""))[:8000] for ch in batch]
            embs = embed_texts(texts, model=model, api_key=api_key, base_url=base_url)
            for ch, vec in zip(batch, embs):
                vectors[ch["chunk_id"]] = np.array(vec, dtype=np.float32)
                embedded_new += 1

    ordered = sorted(parent, key=lambda c: c.get("chunk_id", ""))
    new_manifest: list[dict[str, Any]] = []
    rows: list[np.ndarray] = []
    for ch in ordered:
        cid = ch.get("chunk_id")
        if not cid or cid not in vectors:
            continue
        new_manifest.append(
            {
                "chunk_id": cid,
                "index": len(rows),
                "content_hash": chunk_content_hash(ch),
                "episode_id": ch.get("id"),
                "section": ch.get("section"),
            }
        )
        rows.append(vectors[cid])

    if rows and not _rows_have_uniform_dim(rows) and apply and not force_full_rebuild:
        return build_parent_embeddings(
            apply=apply,
            batch_size=batch_size,
            chunks_path=chunks_path,
            embeddings_path=embeddings_path,
            manifest_path=manifest_path,
            meta_path=meta_path,
            force_full_rebuild=True,
        )

    summary = {
        "parent_chunks": len(parent),
        "reused": len(parent) - len(to_embed),
        "to_embed": len(to_embed),
        "embedded_new": embedded_new if apply else 0,
        "manifest_rows": len(new_manifest),
        "invalidated_cache": invalidated_cache,
    }
    if invalidated_reason:
        summary["invalidated_reason"] = invalidated_reason

    if not apply:
        return summary

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        np.save(embeddings_path, np.stack(rows, axis=0))
        if model:
            _write_embeddings_meta(meta_path, embed_model=model, dim=int(rows[0].shape[0]))
    else:
        if embeddings_path.exists():
            embeddings_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

    with manifest_path.open("w", encoding="utf-8") as f:
        for row in new_manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build parent-tier embedding index")
    parser.add_argument("--dry-run", action="store_true", help="Report counts only")
    args = parser.parse_args()
    summary = build_parent_embeddings(apply=not args.dry_run)
    rel = EMBEDDINGS_PATH.relative_to(ROOT)
    extra = ""
    if summary.get("invalidated_cache"):
        reason = summary.get("invalidated_reason", "")
        extra = f" invalidated=1 reason={reason}" if reason else " invalidated=1"
    print(
        f"parent={summary['parent_chunks']} reuse={summary['reused']} "
        f"embed={summary['to_embed']} rows={summary['manifest_rows']}{extra} -> {rel}"
    )


if __name__ == "__main__":
    main()
