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

from harness.response_report import format_response_markdown, write_response_markdown  # noqa: E402
from harness.scenario_runner import (  # noqa: E402
    ScenarioResult,
    ScenarioRunner,
    TurnResult,
    _check_expectations,
)
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
    assert acc["accounted_breakdown"]["search_wall_ms"] == 4901 + 103972
    assert acc["unaccounted_ms"] == 220600 - (4901 + 103972 + 16345)


def test_timing_accountability_concurrent_many_uses_max_not_sum():
    timing = {
        "vault_search_local_ms": 3608,
        "retrieval_llm_ms": 328105,
        "thread_wait_ms": 74535,
        "searches": [
            {
                "query": "a",
                "tool": "search_vault_many",
                "vault_search_local_ms": 401,
                "retrieval_llm_ms": 15267,
                "wall_ms": 16000,
            },
            {
                "query": "b",
                "tool": "search_vault_many",
                "vault_search_local_ms": 775,
                "retrieval_llm_ms": 57207,
                "wall_ms": 58000,
            },
            {
                "query": "c",
                "tool": "search_vault_many",
                "vault_search_local_ms": 870,
                "retrieval_llm_ms": 57229,
                "wall_ms": 74535,
            },
        ],
        "openrouter_calls": [{"total_ms": 41252}],
    }
    acc = timing_accountability(timing, elapsed_s=124.329)
    assert acc is not None
    assert acc["accounted_breakdown"]["search_wall_ms"] == 74535
    assert acc["accounted_breakdown"]["parallelism_excess_ms"] == 3608 + 328105 - 74535
    assert acc["accounted_ms"] == 74535 + 41252
    assert acc["unaccounted_ms"] == 124329 - (74535 + 41252)


def test_timing_accountability_includes_tool_local():
    timing = {
        "vault_search_local_ms": 0,
        "retrieval_llm_ms": 0,
        "tool_local_ms": 9320,
        "openrouter_calls": [{"total_ms": 9564}],
        "searches": [],
    }
    acc = timing_accountability(timing, elapsed_s=18.884)
    assert acc is not None
    assert acc["accounted_breakdown"]["tool_local_ms"] == 9320
    assert acc["accounted_ms"] == 9320 + 9564
    assert acc["unaccounted_ms"] == 18884 - (9320 + 9564)


def test_enrich_turn_prefers_assistant_content():
    enriched = enrich_turn_from_traces(
        [],
        [_Reply("Searching vault…"), _Reply("<b>HTML answer</b>")],
        elapsed_s=1.0,
        llm_mode="live",
        assistant_content="## Clean **markdown** answer",
    )
    assert enriched["response_text"] == "## Clean **markdown** answer"


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


def test_check_expectations_tool_called_any_passes_when_one_matches():
    traces = [{"step": 1, "tool": "search_vault_many", "arguments": {"queries": ["a"]}}]
    ok, msg = _check_expectations(
        {
            "tool_called_any": ["search_vault", "search_vault_many"],
        },
        replies=[_Reply("answer")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_tool_called_any_fails_when_none_match():
    traces = [{"step": 1, "tool": "search_transcript", "arguments": {"query": "q"}}]
    ok, msg = _check_expectations(
        {
            "tool_called_any": ["search_vault", "search_vault_many"],
        },
        replies=[_Reply("answer")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "expected one of" in msg


def test_check_expectations_tool_called_any_ignored_in_echo_mode():
    ok, msg = _check_expectations(
        {
            "tool_called_any": ["search_vault"],
        },
        replies=[_Reply("answer")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="echo",
    )
    assert ok, msg


def test_check_expectations_not_contains_all_passes_when_absent():
    ok, msg = _check_expectations(
        {"not_contains_all": ["DSML", "redacted_reasoning"]},
        replies=[_Reply("Clean answer about Rockefeller.")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_not_contains_all_fails_on_leak():
    ok, msg = _check_expectations(
        {"not_contains_all": ["DSML", "redacted_reasoning"]},
        replies=[_Reply("Answer with DSML leak.")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "DSML" in msg


def test_check_expectations_episode_citation_passes():
    ok, msg = _check_expectations(
        {"response_contains_episode_citation": True},
        replies=[_Reply("Rockefeller built teams differently [ep-0043].")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_episode_citation_fails_on_loose_ep():
    ok, msg = _check_expectations(
        {"response_contains_episode_citation": True},
        replies=[_Reply("See ep-0043 for details without brackets.")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "[ep-NNNN]" in msg


def test_check_expectations_episode_citation_ignored_in_echo_mode():
    ok, msg = _check_expectations(
        {"response_contains_episode_citation": True},
        replies=[_Reply("No citation here.")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="echo",
    )
    assert ok, msg


def test_check_expectations_tool_called_first_passes():
    traces = [
        {"step": 1, "tool": "search_transcript", "arguments": {"query": "q"}},
        {"step": 2, "tool": "search_vault", "arguments": {"query": "q2"}},
    ]
    ok, msg = _check_expectations(
        {"tool_called_first": "search_transcript"},
        replies=[_Reply("quote [ep-0016]")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_tool_called_first_fails_when_vault_leads():
    traces = [
        {"step": 1, "tool": "search_vault", "arguments": {"query": "q"}},
        {"step": 2, "tool": "search_transcript", "arguments": {"query": "q2"}},
    ]
    ok, msg = _check_expectations(
        {"tool_called_first": "search_transcript"},
        replies=[_Reply("answer")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "first tool" in msg


def test_check_expectations_tool_calls_max_passes():
    traces = [{"step": i, "tool": "search_vault", "arguments": {}} for i in range(3)]
    ok, msg = _check_expectations(
        {"tool_calls_max": 3},
        replies=[_Reply("ok")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_tool_calls_max_fails():
    traces = [{"step": i, "tool": "search_vault", "arguments": {}} for i in range(4)]
    ok, msg = _check_expectations(
        {"tool_calls_max": 3},
        replies=[_Reply("ok")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "tool calls" in msg


def test_check_expectations_tool_rounds_max_passes():
    traces = [
        {"record": "round", "round": 1, "tools": ["search_vault"], "queries": [], "evidence": []},
        {"record": "round", "round": 2, "tools": ["search_vault"], "queries": [], "evidence": []},
    ]
    ok, msg = _check_expectations(
        {"tool_rounds_max": 2},
        replies=[_Reply("decline")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_no_episode_citations_passes():
    ok, msg = _check_expectations(
        {"no_episode_citations": True},
        replies=[_Reply("Nothing on Chesky in the vault.")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_no_episode_citations_fails():
    ok, msg = _check_expectations(
        {"no_episode_citations": True},
        replies=[_Reply("See [ep-0016] anyway.")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok


def test_check_expectations_episode_citations_exclude_passes():
    ok, msg = _check_expectations(
        {"episode_citations_exclude": ["ep-0016"]},
        replies=[_Reply("Vanderbilt delegated differently [ep-0054].")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_episode_citations_exclude_fails():
    ok, msg = _check_expectations(
        {"episode_citations_exclude": ["ep-0016"]},
        replies=[_Reply("Rockefeller anyway [ep-0016].")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "ep-0016" in msg


def test_check_expectations_search_vault_many_queries_min_passes():
    traces = [
        {
            "step": 1,
            "tool": "search_vault_many",
            "arguments": {"queries": ["Edison teams", "Rockefeller teams"]},
        }
    ]
    ok, msg = _check_expectations(
        {"search_vault_many_queries_min": 2},
        replies=[_Reply("Both differ [ep-0043].")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_search_vault_many_queries_min_fails():
    traces = [
        {
            "step": 1,
            "tool": "search_vault_many",
            "arguments": {"queries": ["only one"]},
        }
    ]
    ok, msg = _check_expectations(
        {"search_vault_many_queries_min": 2},
        replies=[_Reply("answer")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert not ok
    assert "sub-queries" in msg


def test_check_expectations_response_contains_all_passes():
    ok, msg = _check_expectations(
        {"response_contains_all": ["Edison", "Rockefeller"]},
        replies=[_Reply("Edison and Rockefeller differed [ep-0043].")],
        tool_traces=[],
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_check_expectations_tools_not_called_passes():
    traces = [{"step": 1, "tool": "search_vault", "arguments": {"query": "q"}}]
    ok, msg = _check_expectations(
        {"tools_not_called": ["load_episode"]},
        replies=[_Reply("decline")],
        tool_traces=traces,
        janitor_phase=None,
        sandbox_inspect=None,
        llm_mode="live",
    )
    assert ok, msg


def test_enrich_turn_includes_observability():
    traces = _verbatim_transcript_traces()
    enriched = enrich_turn_from_traces(
        traces,
        [_Reply("Answer [ep-0016].")],
        elapsed_s=136.0,
        llm_mode="live",
    )
    obs = enriched.get("observability") or {}
    assert obs.get("timing_enabled") is True
    assert obs.get("agent_path", {}).get("path_string")
    assert obs.get("latency", {}).get("synthesis", {}).get("final_ttft_ms") == 11927


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
    report_paths = runner.write_report(results, tmp_path / "runs")
    assert report_paths.markdown is None
    payload = json.loads(report_paths.json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.0"
    assert "harness_version" in payload
    assert payload["scenario_count"] == 1
    assert "generated_at" in payload
    row = payload["scenarios"][0]["turns"][0]
    assert row["response_text"] == "Answer text."
    assert row["stop_reason"] == "natural"
    assert row["tool_calls"][0]["arguments"]["query"] == "q"
    assert row["timing"]["vault_search_local_ms"] == 100
    assert row["timing_accountability"]["unaccounted_ms"] == 9700


def _librarian_turn(**overrides: object) -> TurnResult:
    base = dict(
        index=1,
        action="send 'Who founded Nike?'",
        passed=True,
        message="ok",
        elapsed_s=10.0,
        response_text="Phil Knight built Nike [ep-0123].",
        user_send="Who founded Nike?",
    )
    base.update(overrides)
    return TurnResult(**base)  # type: ignore[arg-type]


def _librarian_result(
    tmp_path: Path,
    *,
    llm_mode: str = "live",
    turns: list[TurnResult] | None = None,
    passed: bool = True,
) -> ScenarioResult:
    return ScenarioResult(
        name="Librarian test",
        path=tmp_path / "dev" / "scenarios" / "librarian" / "basic_qa.yaml",
        passed=passed,
        turns=turns or [_librarian_turn()],
        elapsed_s=10.0,
        llm_mode=llm_mode,
    )


def test_write_response_markdown_live_librarian(tmp_path: Path):
    result = _librarian_result(tmp_path)
    body = format_response_markdown([result])
    assert body is not None
    assert "# Librarian harness responses" in body
    assert "## Librarian test (PASS)" in body
    assert "### Turn 1" in body
    assert "> Who founded Nike?" in body
    assert "Phil Knight built Nike [ep-0123]." in body

    md_path = write_response_markdown([result], tmp_path / "runs", stamp="2026-06-09T18-00-00")
    assert md_path is not None
    assert md_path.name == "2026-06-09T18-00-00-report.md"
    assert "Phil Knight" in md_path.read_text(encoding="utf-8")


def test_write_response_markdown_skips_empty_turns(tmp_path: Path):
    turns = [
        _librarian_turn(index=1, response_text="", user_send="/start"),
        _librarian_turn(index=2, response_text="Follow-up answer."),
    ]
    body = format_response_markdown([_librarian_result(tmp_path, turns=turns)])
    assert body is not None
    assert "### Turn 1" not in body
    assert "### Turn 2" in body
    assert "Follow-up answer." in body


def test_write_response_markdown_skips_echo(tmp_path: Path):
    result = _librarian_result(tmp_path, llm_mode="echo")
    assert format_response_markdown([result]) is None
    assert write_response_markdown([result], tmp_path / "runs", stamp="t") is None


def test_write_response_markdown_skips_janitor_only(tmp_path: Path):
    janitor = ScenarioResult(
        name="Janitor parse",
        path=tmp_path / "dev" / "scenarios" / "janitor" / "episode_parse.yaml",
        passed=True,
        turns=[TurnResult(1, "send '/janitor'", True, "ok", response_text="Janitor")],
        elapsed_s=1.0,
        llm_mode="live",
    )
    assert format_response_markdown([janitor]) is None
