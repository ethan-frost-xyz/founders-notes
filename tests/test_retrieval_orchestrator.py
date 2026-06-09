"""Orchestrator unit tests with mocked expand/rerank LLM calls."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
VAULT_SEARCH_CHUNKS = REPO / "tests" / "fixtures" / "vault_search_chunks.jsonl"

from retrieval_orchestrator import (  # noqa: E402
    EXPAND_VARIANTS_FULL,
    EXPAND_VARIANTS_NONE,
    EvidenceBundle,
    OrchestratorConfig,
    RetrievalOrchestrator,
    format_evidence_for_tool,
    quote_intent,
)


@pytest.fixture
def orch_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        vault_root=REPO,
        model="test/model",
        api_key="test-key",
        search_k=4,
        chunks_path=VAULT_SEARCH_CHUNKS,
    )


def _patch_orchestrator_search(monkeypatch: pytest.MonkeyPatch, *, hybrid_hits: list[dict]) -> None:
    """Patch names bound in retrieval_orchestrator (not only search_retrieval)."""
    import retrieval_orchestrator as ro

    monkeypatch.setattr(ro, "_hybrid_search_parent_chunks", lambda *a, **k: list(hybrid_hits))
    monkeypatch.setattr(ro, "embed_queries", lambda qs: [None] * len(qs))
    monkeypatch.setattr(ro, "search_transcript_keyword", lambda *a, **k: [])


def test_quote_intent_detected():
    assert quote_intent("What did he say about pricing?")


def test_retrieve_core_thematic_with_mocks(orch_config: OrchestratorConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ROOT", str(REPO))

    fake_chunk = {
        "chunk_id": "ep-0016#expanded:x#1",
        "id": "ep-0016",
        "section": "expanded:expanded_datapoints",
        "excerpt": "Quote: competition",
        "title": "Rockefeller",
        "source_path": "content/notes/x.expanded.md",
    }

    def fake_expand(user_message, **kwargs):
        return "Rockefeller competition", ["Rockefeller", "Standard Oil", "monopoly", "trust", "rivals"]

    def fake_rerank(query, candidates, **kwargs):
        return [
            {**candidates[0], "rerank_score": 8.0, "rerank_rationale": "on topic"},
        ]

    _patch_orchestrator_search(monkeypatch, hybrid_hits=[fake_chunk])

    orch = RetrievalOrchestrator(
        orch_config,
        expand_fn=fake_expand,
        rerank_fn=fake_rerank,
    )
    bundle = orch.retrieve_core("Rockefeller competition", expand_variants=EXPAND_VARIANTS_FULL)
    assert bundle.chunks
    assert bundle.chunks[0].section.startswith("expanded:")


def test_retrieve_core_skips_expansion_when_zero(
    orch_config: OrchestratorConfig, monkeypatch: pytest.MonkeyPatch
):
    import retrieval_orchestrator as ro

    expand_called = False

    def fake_expand(user_message, **kwargs):
        nonlocal expand_called
        expand_called = True
        return user_message, [user_message] * 5

    monkeypatch.setattr(ro, "_hybrid_search_parent_chunks", lambda *a, **k: [])
    monkeypatch.setattr(ro, "embed_queries", lambda qs: [None] * len(qs))
    monkeypatch.setattr(ro, "search_transcript_keyword", lambda *a, **k: [])

    orch = RetrievalOrchestrator(orch_config, expand_fn=fake_expand, rerank_fn=lambda *a, **k: [])
    bundle = orch.retrieve_core("Edison teams", expand_variants=EXPAND_VARIANTS_NONE)
    assert expand_called is False
    assert bundle.retrieval_meta.get("expansion_skipped") is True
    assert bundle.retrieval_meta["variants"] == ["Edison teams"]


def test_retrieve_calls_hybrid_search_per_variant(
    orch_config: OrchestratorConfig, monkeypatch: pytest.MonkeyPatch
):
    import retrieval_orchestrator as ro

    call_count = 0

    def counting_hybrid(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return []

    monkeypatch.setattr(ro, "_hybrid_search_parent_chunks", counting_hybrid)
    monkeypatch.setattr(ro, "embed_queries", lambda qs: [None] * len(qs))
    monkeypatch.setattr(ro, "get_embedding_store", lambda **k: None)
    monkeypatch.setattr(ro, "search_transcript_keyword", lambda *a, **k: [])

    variants = ["v1", "v2", "v3", "v4", "v5"]

    def fake_expand(user_message, **kwargs):
        return "standalone query", variants

    def fake_rerank(query, candidates, **kwargs):
        return []

    orch = RetrievalOrchestrator(
        orch_config,
        expand_fn=fake_expand,
        rerank_fn=fake_rerank,
    )
    bundle = orch.retrieve("test query")
    assert call_count == 5
    assert bundle.retrieval_meta["variants"] == variants


def test_retrieve_excludes_summary_from_citable(orch_config: OrchestratorConfig, monkeypatch: pytest.MonkeyPatch):
    _patch_orchestrator_search(monkeypatch, hybrid_hits=[])

    def fake_expand(user_message, **kwargs):
        return user_message, [user_message] * 5

    def fake_rerank(query, candidates, **kwargs):
        return [
            {
                "chunk_id": "ep-0001#summary:episode#1",
                "id": "ep-0001",
                "section": "summary:episode",
                "excerpt": "routing only",
                "rerank_score": 9.0,
            },
            {
                "chunk_id": "ep-0001#expanded:x#1",
                "id": "ep-0001",
                "section": "expanded:expanded_datapoints",
                "excerpt": "Quote: real datapoint",
                "rerank_score": 7.0,
            },
        ]

    orch = RetrievalOrchestrator(
        orch_config,
        expand_fn=fake_expand,
        rerank_fn=fake_rerank,
    )
    bundle = orch.retrieve("theme")
    assert all(not ch.section.startswith("summary:") for ch in bundle.chunks)


def test_format_evidence_for_tool_labels_subquery():
    bundle = EvidenceBundle(
        chunks=[],
        retrieval_meta={},
    )
    text = format_evidence_for_tool(bundle, label="Edison teams")
    assert "Edison teams" in text
    assert "No citable evidence" in text
