"""Orchestrator unit tests with mocked expand/rerank LLM calls."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from retrieval_orchestrator import (  # noqa: E402
    EvidenceBundle,
    OrchestratorConfig,
    RetrievalOrchestrator,
    classify_intent,
    quote_intent,
)


@pytest.fixture
def orch_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        vault_root=REPO,
        model="test/model",
        api_key="test-key",
        search_k=4,
    )


def test_classify_meta_greeting():
    assert classify_intent("hello", None) == "meta"


def test_classify_thematic_default():
    assert classify_intent("What did Rockefeller believe about competition?", None) == "thematic"


def test_quote_intent_detected():
    assert quote_intent("What did he say about pricing?")


def test_retrieve_meta_skips_search(orch_config: OrchestratorConfig):
    orch = RetrievalOrchestrator(orch_config)
    bundle = orch.retrieve("hello")
    assert bundle.skip_retrieval
    assert bundle.chunks == []


def test_retrieve_thematic_with_mocks(orch_config: OrchestratorConfig, monkeypatch: pytest.MonkeyPatch):
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

    import search_retrieval as sr

    monkeypatch.setattr(sr, "_hybrid_search_parent_chunks", lambda *a, **k: [fake_chunk])
    monkeypatch.setattr(sr, "embed_queries", lambda qs: [None] * len(qs))
    monkeypatch.setattr(sr, "search_transcript_keyword", lambda *a, **k: [])

    orch = RetrievalOrchestrator(
        orch_config,
        expand_fn=fake_expand,
        rerank_fn=fake_rerank,
    )
    bundle = orch.retrieve("Rockefeller competition")
    assert not bundle.skip_retrieval
    assert bundle.chunks
    assert bundle.chunks[0].section.startswith("expanded:")


def test_retrieve_excludes_summary_from_citable(orch_config: OrchestratorConfig, monkeypatch: pytest.MonkeyPatch):
    import search_retrieval as sr

    monkeypatch.setattr(sr, "_hybrid_search_parent_chunks", lambda *a, **k: [])
    monkeypatch.setattr(sr, "embed_queries", lambda qs: [None] * len(qs))
    monkeypatch.setattr(sr, "search_transcript_keyword", lambda *a, **k: [])

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
