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
import os
from typing import Any

import numpy as np
from dotenv import load_dotenv

from paths import CHUNKS_PATH, EMBEDDINGS_MANIFEST_PATH, EMBEDDINGS_PATH, ROOT
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


def build_parent_embeddings(
    *,
    apply: bool = True,
    batch_size: int = 32,
    chunks_path: Path | None = None,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Incremental parent-only vectors aligned to manifest row index."""
    chunks_path = chunks_path or CHUNKS_PATH
    embeddings_path = embeddings_path or EMBEDDINGS_PATH
    manifest_path = manifest_path or EMBEDDINGS_MANIFEST_PATH

    parent = parent_chunks_for_embedding(load_chunks(chunks_path))
    old_manifest = load_embeddings_manifest(manifest_path)
    old_by_id = {row["chunk_id"]: row for row in old_manifest if row.get("chunk_id")}

    old_matrix = None
    if embeddings_path.exists() and old_manifest:
        old_matrix = np.load(embeddings_path)

    vectors: dict[str, np.ndarray] = {}
    for row in old_manifest:
        cid = row.get("chunk_id")
        idx = row.get("index")
        if cid is None or idx is None or old_matrix is None:
            continue
        ch = next((c for c in parent if c.get("chunk_id") == cid), None)
        if ch and old_by_id.get(cid, {}).get("content_hash") == chunk_content_hash(ch):
            vectors[cid] = old_matrix[int(idx)]

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("OPENROUTER_EMBED_MODEL", "").strip()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or None

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

    summary = {
        "parent_chunks": len(parent),
        "reused": len(parent) - len(to_embed),
        "to_embed": len(to_embed),
        "embedded_new": embedded_new if apply else 0,
        "manifest_rows": len(new_manifest),
    }

    if not apply:
        return summary

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        np.save(embeddings_path, np.stack(rows, axis=0))
    elif embeddings_path.exists():
        embeddings_path.unlink()

    with manifest_path.open("w", encoding="utf-8") as f:
        import json

        for row in new_manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build parent-tier embedding index")
    parser.add_argument("--dry-run", action="store_true", help="Report counts only")
    args = parser.parse_args()
    summary = build_parent_embeddings(apply=not args.dry_run)
    rel = EMBEDDINGS_PATH.relative_to(ROOT)
    print(
        f"parent={summary['parent_chunks']} reuse={summary['reused']} "
        f"embed={summary['to_embed']} rows={summary['manifest_rows']} -> {rel}"
    )


if __name__ == "__main__":
    main()
