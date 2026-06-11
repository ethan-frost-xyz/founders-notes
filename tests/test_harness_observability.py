"""Unit tests for harness observability derivations."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DEV = REPO / "dev"
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.observability import (  # noqa: E402
    agent_path_from_traces,
    build_observability,
    cap_thrash_from_traces,
    latency_from_traces,
    spans_from_traces,
)
def _verbatim_transcript_traces() -> list[dict]:
    """Minimal cap-hit trace fixture."""
    traces: list[dict] = [
        {"step": 1, "tool": "search_transcript", "arguments": {"query": "q1"}},
        {"step": 1, "tool": "search_vault", "arguments": {"query": "q2"}},
        {
            "record": "round",
            "round": 1,
            "tools": ["search_transcript", "search_vault"],
            "queries": ["q1", "q2"],
            "evidence": [{"episode_id": "ep-0016", "chunk_id": "c1", "rerank_score": 7.5}],
            "episode_ids": ["ep-0016"],
            "reasoning": "",
        },
        {
            "record": "timing",
            "stop_reason": "cap",
            "tool_local_ms": 0,
            "openrouter_calls": [
                {"label": "agent_round_6", "total_ms": 9498, "ttft_ms": 6211},
                {"label": "agent_round_7_cap", "total_ms": 12479, "ttft_ms": 11927},
            ],
        },
    ]
    return traces


def _traces_with_spans() -> list[dict]:
    traces = _verbatim_transcript_traces()
    traces.insert(
        -1,
        {
            "record": "spans",
            "spans": [
                {"name": "agent.routing", "ms": 9498, "attrs": {"round": 6}},
                {"name": "agent.synthesis.final", "ms": 12479, "attrs": {"stop": "cap"}},
                {"name": "retrieval.query_expand", "ms": 12000},
                {"name": "retrieval.hybrid_search", "ms": 800},
                {"name": "retrieval.llm_rerank", "ms": 45000},
            ],
        },
    )
    return traces


def test_spans_from_traces():
    spans = spans_from_traces(_traces_with_spans())
    assert len(spans) == 5
    assert spans[0]["name"] == "agent.routing"


def test_agent_path_string():
    path = agent_path_from_traces(_verbatim_transcript_traces())
    assert path["sequence"][0] == "search_transcript"
    assert "search_vault" in path["path_string"]
    assert path["tool_rounds_used"] == 1


def test_cap_thrash_gathered_and_cited():
    from harness.trace_report import tool_rounds_from_traces

    rounds = tool_rounds_from_traces(_verbatim_transcript_traces())
    thrash = cap_thrash_from_traces(
        rounds,
        stop_reason="cap",
        response_text="Rockefeller said competition [ep-0016] is good.",
    )
    assert thrash is not None
    assert thrash["hit_cap"] is True
    assert thrash["gathered"]["total_unique_chunks"] == 1
    assert "ep-0016" in thrash["cited"]["episodes_in_response"]


def test_latency_final_synthesis_ttft():
    from harness.trace_report import timing_dict_from_traces

    traces = _traces_with_spans()
    timing = timing_dict_from_traces(traces)
    latency = latency_from_traces(
        traces,
        elapsed_s=136.0,
        timing=timing,
        stop_reason="cap",
        accountability=None,
    )
    assert latency["synthesis"]["final_ttft_ms"] == 11927
    assert latency["synthesis"]["label"] == "agent_round_7_cap"
    assert latency["agent_routing_ms"] == 9498
    assert latency["retrieval"]["query_expand_ms"] == 12000


def test_build_observability_disabled_without_timing():
    obs = build_observability(
        [],
        response_text="",
        elapsed_s=1.0,
        timing=None,
        stop_reason="natural",
        accountability=None,
        tool_rounds=[],
        timing_enabled=False,
    )
    assert obs["timing_enabled"] is False


def test_build_observability_full():
    from harness.trace_report import timing_dict_from_traces, tool_rounds_from_traces

    traces = _traces_with_spans()
    timing = timing_dict_from_traces(traces)
    rounds = tool_rounds_from_traces(traces)
    obs = build_observability(
        traces,
        response_text="Answer [ep-0016].",
        elapsed_s=136.0,
        timing=timing,
        stop_reason="cap",
        accountability=None,
        tool_rounds=rounds,
    )
    assert obs["timing_enabled"] is True
    assert obs["agent_path"]["path_string"]
    assert obs["cap_thrash"] is not None
    assert obs["synthesis_quality"]["citation_count"] == 1
