"""Unit tests for LLM reranker (ingestion/lib/rerank_llm.py)."""

from __future__ import annotations

import json

import pytest

from openrouter_client import OpenRouterCompletion
from rerank_llm import rerank_candidates


def _fake_completion(payload: dict) -> OpenRouterCompletion:
    return OpenRouterCompletion(
        content=json.dumps(payload),
        response_id=None,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=None,
        duration_ms=1,
    )


def test_rerank_skips_hallucinated_chunk_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = [
        {"chunk_id": "ep-0010#expanded:expanded_datapoints#1", "excerpt": "real hit"},
        {"chunk_id": "ep-0022#transcript:transcript#5", "excerpt": "other"},
    ]

    def fake_call_openrouter(**kwargs):
        return _fake_completion(
            {
                "ranked": [
                    {
                        "chunk_id": "ep-9999#expanded:expanded_datapoints#99",
                        "score": 10.0,
                        "rationale": "hallucinated",
                    },
                    {
                        "chunk_id": "ep-0010#expanded:expanded_datapoints#1",
                        "score": 8.0,
                        "rationale": "on topic",
                    },
                ]
            }
        )

    monkeypatch.setattr("openrouter_client.call_openrouter", fake_call_openrouter)

    ranked = rerank_candidates(
        "Phil Knight book",
        candidates,
        model="test/model",
        api_key="test-key",
    )

    assert len(ranked) == 2
    assert ranked[0]["chunk_id"] == "ep-0010#expanded:expanded_datapoints#1"
    assert ranked[0]["rerank_score"] == 8.0
    assert ranked[1]["chunk_id"] == "ep-0022#transcript:transcript#5"
    assert ranked[1]["rerank_score"] == 0.0


def test_rerank_only_hallucinated_ids_falls_back_to_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        {"chunk_id": "ep-0010#expanded:expanded_datapoints#1", "excerpt": "a"},
    ]

    monkeypatch.setattr(
        "openrouter_client.call_openrouter",
        lambda **kwargs: _fake_completion(
            {
                "ranked": [
                    {"chunk_id": "ep-9999#expanded:expanded_datapoints#1", "score": 9.0},
                ]
            }
        ),
    )

    ranked = rerank_candidates("query", candidates, model="m", api_key="k")

    assert len(ranked) == 1
    assert ranked[0]["chunk_id"] == "ep-0010#expanded:expanded_datapoints#1"
    assert ranked[0]["rerank_score"] == 0.0
