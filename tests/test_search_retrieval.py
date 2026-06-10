"""Tests for vault search_retrieval (fixture slice, no API)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

import paths
from search_retrieval import (
    chunk_content_hash,
    hybrid_search_parent_chunks,
    chunks_needing_embedding,
    episode_is_studied,
    excerpt_hash,
    get_chunk_index,
    hybrid_search_parent,
    invalidate_chunk_index_cache,
    invalidate_studied_episode_cache,
    is_parent_chunk,
    is_transcript_chunk,
    parent_chunks_for_embedding,
    search_chunks_keyword,
    structured_embed_text,
    studied_episode_ids,
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
    assert len(parents) == 3
    assert len(transcripts) == 1
    assert any(c["section"].startswith("expanded:") for c in parents)
    assert any(c["section"].startswith("summary:") for c in parents)
    assert not any(c["section"].startswith(("notes:", "post:")) for c in parents)


def test_keyword_parent_search():
    chunks = load_fixture()
    hits = search_chunks_keyword(
        "customer",
        8,
        chunks=chunks,
        chunk_predicate=is_parent_chunk,
    )
    assert hits
    assert hits[0][1]["section"].startswith(("expanded:", "summary:"))


def test_keyword_multi_term_overlap():
    chunks = load_fixture()
    hits = search_chunks_keyword(
        "customer focus quality",
        8,
        chunks=chunks,
        chunk_predicate=is_parent_chunk,
    )
    assert hits
    assert hits[0][0] >= 2.0


def test_chunk_to_hit_prefers_stored_excerpt():
    from search_retrieval import chunk_to_hit

    ch = {
        "chunk_id": "ep-0099#expanded:expanded_datapoints#1",
        "id": "ep-0099",
        "section": "expanded:expanded_datapoints",
        "source_path": "content/notes/ep-0099-example/ep-0099-example.expanded.md",
        "start_line": 1,
        "excerpt": "Quote: inner scorecard lesson here",
    }
    hit = chunk_to_hit(ch, root=Path("/nonexistent"))
    assert hit["excerpt"] == "Quote: inner scorecard lesson here"
    assert "inner scorecard" in hit["excerpt"]


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


def test_studied_episode_ids_cache_invalidates_on_notes_touch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    catalog = tmp_path / "catalog" / "episodes.jsonl"
    monkeypatch.setattr(paths, "CATALOG_PATH", catalog)
    monkeypatch.setattr(paths, "CHUNKS_PATH", tmp_path / "catalog" / "chunks.jsonl")
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        '{"id":"ep-0001","slug":"1-test","episode_number":1}\n',
        encoding="utf-8",
    )
    notes_dir = tmp_path / "content" / "notes" / "ep-0001-test"
    notes_dir.mkdir(parents=True)
    npath = notes_dir / "ep-0001-test.notes.md"
    npath.write_text(
        "---\ntitle: T\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )
    invalidate_studied_episode_cache()
    assert "ep-0001" in studied_episode_ids(root=tmp_path)

    import time

    time.sleep(0.02)
    npath.write_text(
        "---\ntitle: T\n---\n\n## Raw datapoints\n\n",
        encoding="utf-8",
    )
    assert "ep-0001" not in studied_episode_ids(root=tmp_path)

    time.sleep(0.02)
    npath.write_text(
        "---\ntitle: T\n---\n\n## Raw datapoints\n\n- 2:00 — new hook\n",
        encoding="utf-8",
    )
    assert "ep-0001" in studied_episode_ids(root=tmp_path)


def test_episode_is_studied_fast_after_prime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import paths as vault_paths

    monkeypatch.setattr(vault_paths, "ROOT", tmp_path)
    catalog = tmp_path / "catalog" / "episodes.jsonl"
    monkeypatch.setattr(vault_paths, "CATALOG_PATH", catalog)
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        '{"id":"ep-0001","slug":"1-test","episode_number":1}\n',
        encoding="utf-8",
    )
    notes_dir = tmp_path / "content" / "notes" / "ep-0001-test"
    notes_dir.mkdir(parents=True)
    (notes_dir / "ep-0001-test.notes.md").write_text(
        "---\ntitle: T\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )
    invalidate_studied_episode_cache()
    studied_episode_ids(root=tmp_path)

    t0 = time.perf_counter()
    for _ in range(1000):
        assert episode_is_studied("ep-0001", root=tmp_path)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 50, f"episode_is_studied loop took {elapsed_ms:.1f}ms"


def test_get_chunk_index_caches_by_mtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import paths as vault_paths

    monkeypatch.setattr(vault_paths, "ROOT", tmp_path)
    catalog = tmp_path / "catalog" / "episodes.jsonl"
    chunks_path = tmp_path / "catalog" / "chunks.jsonl"
    monkeypatch.setattr(vault_paths, "CATALOG_PATH", catalog)
    monkeypatch.setattr(vault_paths, "CHUNKS_PATH", chunks_path)
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        '{"id":"ep-0090","slug":"90-test","episode_number":90}\n',
        encoding="utf-8",
    )
    notes_dir = tmp_path / "content" / "notes" / "ep-0090-test"
    notes_dir.mkdir(parents=True)
    (notes_dir / "ep-0090-test.notes.md").write_text(
        "---\ntitle: T\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )
    chunks_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    invalidate_studied_episode_cache()
    invalidate_chunk_index_cache()

    first = get_chunk_index(chunks_path=chunks_path, root=tmp_path)
    second = get_chunk_index(chunks_path=chunks_path, root=tmp_path)
    assert first is second
    assert len(first.parent_chunks) >= 1

    time.sleep(0.02)
    chunks_path.write_text(chunks_path.read_text(encoding="utf-8"), encoding="utf-8")
    third = get_chunk_index(chunks_path=chunks_path, root=tmp_path)
    assert third is not second


def test_hybrid_search_reuses_shared_index():
    index = get_chunk_index(chunks_path=FIXTURE)
    load_calls = 0
    original = index.all_chunks

    def counting_load(path=None):
        nonlocal load_calls
        load_calls += 1
        return original

    with patch("search_chunk_index.load_chunks", side_effect=counting_load):
        hybrid_search_parent_chunks("customer", 3, index=index, query_vector=None)
        hybrid_search_parent_chunks("focus", 3, index=index, query_vector=None)
    assert load_calls == 0


def test_structured_embed_text_expanded_fields():
    ch = {
        "section": "expanded:expanded_datapoints",
        "title": "Test",
        "id": "ep-0001",
        "episode_number": 1,
        "published_at": "2016-01-01",
        "excerpt": (
            "### 10:00 — Hook\n\nContext: setup.\n\n"
            "Quote: exact words.\n\nKey takeaway: lesson."
        ),
    }
    text = structured_embed_text(ch)
    assert "Timestamp: 10:00" in text
    assert "Quote: exact words" in text
    assert "Takeaway: lesson" in text


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


def _import_build_embeddings():
    import sys

    search_dir = paths.INGESTION_DIR / "search"
    if str(search_dir) not in sys.path:
        sys.path.insert(0, str(search_dir))
    import build_embeddings

    return build_embeddings


def _write_embedding_cache(
    tmp_path: Path,
    parent: list[dict],
    *,
    dim: int = 4,
    embed_model: str | None = None,
) -> tuple[Path, Path, Path, Path]:
    manifest_path = tmp_path / "manifest.jsonl"
    emb_path = tmp_path / "embeddings.npy"
    meta_path = tmp_path / "embeddings-meta.json"
    manifest = [
        {"chunk_id": ch["chunk_id"], "index": i, "content_hash": chunk_content_hash(ch)}
        for i, ch in enumerate(sorted(parent, key=lambda c: c["chunk_id"]))
    ]
    manifest_path.write_text(
        "\n".join(json.dumps(r) for r in manifest) + "\n",
        encoding="utf-8",
    )
    np.save(emb_path, np.zeros((len(manifest), dim), dtype=np.float32))
    if embed_model is not None:
        meta_path.write_text(
            json.dumps({"embed_model": embed_model, "dim": dim}) + "\n",
            encoding="utf-8",
        )
    return manifest_path, emb_path, meta_path, tmp_path / "chunks.jsonl"


def test_build_embeddings_reuses_manifest_without_api(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    parent = parent_chunks_for_embedding(load_fixture())
    manifest_path, emb_path, meta_path, _ = _write_embedding_cache(
        tmp_path, parent, embed_model="fixture/reuse-model"
    )
    monkeypatch.setenv("OPENROUTER_EMBED_MODEL", "fixture/reuse-model")

    build_embeddings = _import_build_embeddings()
    monkeypatch.setattr(
        build_embeddings,
        "embed_texts",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call API")),
    )
    from build_embeddings import build_parent_embeddings

    summary = build_parent_embeddings(
        apply=True,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=manifest_path,
        meta_path=meta_path,
    )
    assert summary["to_embed"] == 0
    assert summary["reused"] == len(parent)
    assert not summary.get("invalidated_cache")


def test_build_embeddings_reembeds_when_matrix_missing(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    parent = parent_chunks_for_embedding(load_fixture())
    manifest_path, emb_path, meta_path, _ = _write_embedding_cache(
        tmp_path, parent, embed_model="fixture/missing-matrix"
    )
    emb_path.unlink()
    assert not emb_path.exists()
    monkeypatch.setenv("OPENROUTER_EMBED_MODEL", "fixture/missing-matrix")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    build_embeddings = _import_build_embeddings()

    def fake_embed(texts, **kwargs):
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(build_embeddings, "embed_texts", fake_embed)
    from build_embeddings import build_parent_embeddings

    summary = build_parent_embeddings(
        apply=True,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=manifest_path,
        meta_path=meta_path,
    )
    assert summary["to_embed"] == len(parent)
    assert emb_path.is_file()
    saved = np.load(emb_path)
    assert saved.shape[0] == len(parent)


def test_build_embeddings_invalidates_on_embed_model_mismatch(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    parent = parent_chunks_for_embedding(load_fixture())
    manifest_path, emb_path, meta_path, _ = _write_embedding_cache(
        tmp_path, parent, embed_model="old/embed-model"
    )
    monkeypatch.setenv("OPENROUTER_EMBED_MODEL", "new/embed-model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    build_embeddings = _import_build_embeddings()
    calls: list[int] = []

    def fake_embed(texts, **kwargs):
        calls.append(len(texts))
        return [[0.0] * 8 for _ in texts]

    monkeypatch.setattr(build_embeddings, "embed_texts", fake_embed)
    from build_embeddings import build_parent_embeddings

    summary = build_parent_embeddings(
        apply=True,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=manifest_path,
        meta_path=meta_path,
    )
    assert summary["invalidated_cache"]
    assert summary.get("invalidated_reason") == "embed_model_changed"
    assert summary["to_embed"] == len(parent)
    assert calls
    saved = np.load(emb_path)
    assert saved.shape == (len(parent), 8)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["embed_model"] == "new/embed-model"
    assert meta["dim"] == 8


def test_build_embeddings_invalidates_on_dim_mismatch_without_meta(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    parent = parent_chunks_for_embedding(load_fixture())
    manifest_path, emb_path, meta_path, _ = _write_embedding_cache(tmp_path, parent)
    assert not meta_path.exists()
    monkeypatch.setenv("OPENROUTER_EMBED_MODEL", "probe/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    build_embeddings = _import_build_embeddings()
    monkeypatch.setattr(build_embeddings, "_probe_embedding_dim", lambda **k: 8)

    def fake_embed(texts, **kwargs):
        return [[0.0] * 8 for _ in texts]

    monkeypatch.setattr(build_embeddings, "embed_texts", fake_embed)
    from build_embeddings import build_parent_embeddings

    summary = build_parent_embeddings(
        apply=True,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=manifest_path,
        meta_path=meta_path,
    )
    assert summary["invalidated_cache"]
    assert summary.get("invalidated_reason") == "legacy_dim_probe_mismatch"
    assert summary["to_embed"] == len(parent)


def test_rows_have_uniform_dim():
    build_embeddings = _import_build_embeddings()
    assert build_embeddings._rows_have_uniform_dim([])
    assert build_embeddings._rows_have_uniform_dim(
        [np.zeros(4, dtype=np.float32), np.ones(4, dtype=np.float32)]
    )
    assert not build_embeddings._rows_have_uniform_dim(
        [np.zeros(4, dtype=np.float32), np.zeros(8, dtype=np.float32)]
    )


def test_build_embeddings_reactive_mixed_dims_retries(tmp_path, monkeypatch):
    chunks_path = tmp_path / "chunks.jsonl"
    fixture_rows = load_fixture()
    parent = parent_chunks_for_embedding(fixture_rows)
    manifest_path, emb_path, meta_path, _ = _write_embedding_cache(
        tmp_path, parent, embed_model="fixture/reactive"
    )
    fixture_rows[0] = {**fixture_rows[0], "excerpt": "changed excerpt forces re-embed"}
    chunks_path.write_text(
        "\n".join(json.dumps(r) for r in fixture_rows) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_EMBED_MODEL", "fixture/reactive")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    build_embeddings = _import_build_embeddings()
    batch_sizes: list[int] = []

    call_n = {"n": 0}

    def fake_embed(texts, **kwargs):
        batch_sizes.append(len(texts))
        call_n["n"] += 1
        dim = 8 if call_n["n"] == 1 else 4
        return [[0.0] * dim for _ in texts]

    monkeypatch.setattr(build_embeddings, "embed_texts", fake_embed)
    from build_embeddings import build_parent_embeddings

    summary = build_parent_embeddings(
        apply=True,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=manifest_path,
        meta_path=meta_path,
    )
    assert summary.get("invalidated_reason") == "force_full_rebuild"
    assert summary["to_embed"] == len(parent_chunks_for_embedding(fixture_rows))
    assert len(batch_sizes) >= 2
    saved = np.load(emb_path)
    assert saved.shape[1] == 4
