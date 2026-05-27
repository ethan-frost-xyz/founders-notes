"""Tests for vault search_retrieval (fixture slice, no API)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import paths
from search_retrieval import (
    chunk_content_hash,
    chunks_needing_embedding,
    excerpt_hash,
    hybrid_search_parent,
    is_parent_chunk,
    is_transcript_chunk,
    parent_chunks_for_embedding,
    search_chunks_keyword,
)

FIXTURE = paths.INGESTION_DIR / "fixtures" / "chunks_parent_slice.jsonl"


def load_fixture() -> list[dict]:
    rows = []
    with FIXTURE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_parent_transcript_filters():
    chunks = load_fixture()
    parents = [c for c in chunks if is_parent_chunk(c)]
    transcripts = [c for c in chunks if is_transcript_chunk(c)]
    assert len(parents) == 4
    assert len(transcripts) == 1
    assert any(c["section"].startswith("expanded:") for c in parents)


def test_keyword_parent_search():
    chunks = load_fixture()
    hits = search_chunks_keyword(
        "customer",
        8,
        chunks=chunks,
        predicate=is_parent_chunk,
    )
    assert hits
    assert hits[0][1]["section"].startswith(("expanded:", "notes:", "post:"))


def test_hybrid_prefers_expanded_section_boost():
    chunks = load_fixture()
    result = hybrid_search_parent(
        "customer focus",
        k=3,
        chunks_path=FIXTURE,
        embeddings_path=Path("/nonexistent/embeddings.npy"),
        manifest_path=Path("/nonexistent/manifest.jsonl"),
    )
    assert result["meta"]["tier"] == "parent"
    assert len(result["hits"]) >= 1
    sections = [h["section"] for h in result["hits"]]
    assert any(s.startswith("expanded:") for s in sections)


def test_excerpt_hash_stable_for_incremental_skip():
    text = "stable excerpt text"
    assert excerpt_hash(text) == excerpt_hash(text)
    assert excerpt_hash(text) != excerpt_hash(text + " ")


def test_chunks_needing_embedding_skips_unchanged_manifest():
    chunks = parent_chunks_for_embedding(load_fixture())
    manifest = [
        {"chunk_id": ch["chunk_id"], "content_hash": chunk_content_hash(ch)}
        for ch in chunks
    ]
    assert chunks_needing_embedding(chunks, manifest) == []


def test_build_embeddings_reuses_manifest_without_api(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    manifest_path = tmp_path / "manifest.jsonl"
    emb_path = tmp_path / "embeddings.npy"

    parent = parent_chunks_for_embedding(load_fixture())
    import json

    manifest = [
        {"chunk_id": ch["chunk_id"], "index": i, "content_hash": chunk_content_hash(ch)}
        for i, ch in enumerate(sorted(parent, key=lambda c: c["chunk_id"]))
    ]
    manifest_path.write_text(
        "\n".join(json.dumps(r) for r in manifest) + "\n",
        encoding="utf-8",
    )
    np.save(emb_path, np.zeros((len(manifest), 4), dtype=np.float32))

    monkeypatch.setattr(
        "build_embeddings.embed_texts",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call API")),
    )

    import sys

    search_dir = paths.INGESTION_DIR / "search"
    if str(search_dir) not in sys.path:
        sys.path.insert(0, str(search_dir))
    from build_embeddings import build_parent_embeddings

    summary = build_parent_embeddings(
        apply=True,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=manifest_path,
    )
    assert summary["to_embed"] == 0
    assert summary["reused"] == len(parent)
