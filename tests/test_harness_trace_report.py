"""Unit tests for harness trace report extractors and enriched JSON reports."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DEV = REPO / "dev"
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.scenario_runner import ScenarioResult, ScenarioRunner, TurnResult  # noqa: E402
from harness.trace_report import (  # noqa: E402
    enrich_turn_from_traces,
    response_text_from_replies,
    stop_reason_from_traces,
    timing_accountability,
    tool_call_counts_from_traces,
    tool_calls_from_traces,
    tool_rounds_from_traces,
)


@dataclass
class _Reply:
    text: str


def _verbatim_transcript_traces() -> list[dict]:
  """Shape from run #11: 11× search_transcript, cap synthesis."""
  traces: list[dict] = [
      {
          "step": 1,
          "tool": "search_transcript",
          "arguments": {"query": "Rockefeller competition exact words"},
      },
  ]
  for i in range(2, 12):
      traces.append(
          {
              "step": 1,
              "tool": "search_transcript",
              "arguments": {"query": f"variant query {i}"},
          }
      )
  traces.append(
      {
          "step": 1,
          "tool": "search_vault",
          "arguments": {"query": "Rockefeller quotes about competition exact words"},
      }
  )
  traces.append(
      {
          "record": "round",
          "round": 1,
          "tools": ["search_transcript", "search_vault"],
          "queries": ["Rockefeller competition exact words", "Rockefeller quotes about competition exact words"],
          "evidence": [{"episode_id": "ep-0016", "rerank_score": 7.5}],
          "reasoning": "",
      }
  )
  traces.append(
      {
          "record": "timing",
          "vault_search_local_ms": 2345,
          "retrieval_llm_ms": 281843,
          "stop_reason": "cap",
          "searches": [
              {
                  "query": "Rockefeller quotes about competition exact words",
                  "tool": "search_vault",
                  "vault_search_local_ms": 1909,
                  "retrieval_llm_ms": 281843,
              }
          ],
          "openrouter_calls": [
              {"label": "agent_round_6", "total_ms": 9498, "ttft_ms": 6211, "completion_tokens": 374},
              {"label": "agent_round_7_cap", "total_ms": 12479, "ttft_ms": 11927, "completion_tokens": 781},
          ],
      }
  )
  return traces


def test_response_text_from_replies_joins_non_empty():
    text = response_text_from_replies(
        [_Reply("Hello"), _Reply(""), _Reply("World")]
    )
    assert text == "Hello\n\nWorld"


def test_tool_calls_from_traces_skips_round_and_timing_rows():
    traces = _verbatim_transcript_traces()
    calls = tool_calls_from_traces(traces)
    assert len(calls) == 12
    assert calls[0]["tool"] == "search_transcript"
    assert calls[0]["arguments"]["query"] == "Rockefeller competition exact words"


def test_tool_call_counts_from_traces():
    counts = tool_call_counts_from_traces(_verbatim_transcript_traces())
    assert counts["search_transcript"] == 11
    assert counts["search_vault"] == 1


def test_stop_reason_from_timing_cap_label():
    traces = _verbatim_transcript_traces()
    assert stop_reason_from_traces(traces) == "cap"


def test_stop_reason_prefers_timing_record():
    traces = [
        {"record": "timing", "stop_reason": "natural", "openrouter_calls": []},
    ]
    assert stop_reason_from_traces(traces) == "natural"


def test_tool_rounds_extracts_episodes_and_scores():
    rounds = tool_rounds_from_traces(_verbatim_transcript_traces())
    assert len(rounds) == 1
    assert rounds[0]["episode_ids"] == ["ep-0016"]
    assert rounds[0]["rerank_scores_top3"] == [7.5]


def test_timing_accountability_math():
    timing = {
        "vault_search_local_ms": 4901,
        "retrieval_llm_ms": 103972,
        "openrouter_calls": [
            {"total_ms": 2414},
            {"total_ms": 2460},
            {"total_ms": 11471},
        ],
    }
    acc = timing_accountability(timing, elapsed_s=220.6)
    assert acc is not None
    assert acc["wall_ms"] == 220600
    assert acc["accounted_breakdown"]["openrouter_total_ms"] == 16345
    assert acc["unaccounted_ms"] == 220600 - (4901 + 103972 + 16345)


def test_enrich_turn_from_traces_includes_accountability():
    enriched = enrich_turn_from_traces(
        _verbatim_transcript_traces(),
        [_Reply("Rockefeller said competition is a sin [ep-0016].")],
        elapsed_s=371.8,
        llm_mode="live",
    )
    assert "Rockefeller" in enriched["response_text"]
    assert enriched["stop_reason"] == "cap"
    assert enriched["tool_call_counts"]["search_transcript"] == 11
    assert enriched["timing_accountability"]["wall_ms"] == 371800


def test_scenario_runner_write_report_includes_tier1_fields(tmp_path: Path):
    runner = ScenarioRunner(verbose=False)
    turn = TurnResult(
        index=1,
        action="send 'test'",
        passed=True,
        message="ok",
        elapsed_s=10.0,
        tools_called=["search_vault"],
        timing={"vault_search_local_ms": 100, "retrieval_llm_ms": 200, "openrouter_calls": []},
        timing_summary="vault=100ms retrieval_llm=200ms",
        response_text="Answer text.",
        stop_reason="natural",
        tool_calls=[{"step": 1, "tool": "search_vault", "arguments": {"query": "q"}}],
        tool_rounds=[{"round": 1, "tools": ["search_vault"], "queries": ["q"], "episode_ids": [], "rerank_scores_top3": []}],
        tool_call_counts={"search_vault": 1},
        trace_summary="stop: natural",
        timing_accountability={"wall_ms": 10000, "accounted_ms": 300, "unaccounted_ms": 9700, "accounted_breakdown": {}},
    )
    results = [
        ScenarioResult(
            name="Test scenario",
            path=tmp_path / "test.yaml",
            passed=True,
            turns=[turn],
            elapsed_s=10.0,
            llm_mode="live",
        )
    ]
    out = runner.write_report(results, tmp_path / "runs")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["scenario_count"] == 1
    assert "generated_at" in payload
    row = payload["scenarios"][0]["turns"][0]
    assert row["response_text"] == "Answer text."
    assert row["stop_reason"] == "natural"
    assert row["tool_calls"][0]["arguments"]["query"] == "q"
    assert row["timing"]["vault_search_local_ms"] == 100
    assert row["timing_accountability"]["unaccounted_ms"] == 9700


def test_search_vault_records_search_on_exception(
    agent_config, monkeypatch: pytest.MonkeyPatch
):
    bot_dir = REPO / "services" / "telegram" / "bot"
    ingestion = REPO / "ingestion"
    for entry in (str(ingestion), str(bot_dir), str(bot_dir / "tools")):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    from retrieval import search_vault_for_turn
    from turn_timing import TurnTimer

    def boom(*args, **kwargs):
        raise RuntimeError("retrieve failed")

    monkeypatch.setattr(
        "retrieval_orchestrator.RetrievalOrchestrator.retrieve_core",
        boom,
    )

    timer = TurnTimer()
    with pytest.raises(RuntimeError, match="retrieve failed"):
        search_vault_for_turn("Rockefeller", config=agent_config, timing=timer)

    d = timer.to_dict()
    assert len(d["searches"]) == 1
    assert d["searches"][0]["tool"] == "search_vault"
    assert d["searches"][0]["error"] is True
