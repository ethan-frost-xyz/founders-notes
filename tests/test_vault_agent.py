"""Vault agent: tool wiring and mock OpenRouter contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent

from agent import (  # noqa: E402
    EMPTY_SYNTHESIS,
    MAX_TOOL_ROUNDS,
    VaultAgent,
    TurnResult,
    _search_budget_nudge,
    build_trace_summary,
    execute_tool,
    openrouter_tools,
)
from config import AgentConfig  # noqa: E402
from tool_status import tool_status_label  # noqa: E402


def test_openrouter_tools_includes_five_toolbox():
    names = [t["function"]["name"] for t in openrouter_tools()]
    assert names == [
        "search_vault",
        "search_vault_many",
        "search_transcript",
        "load_episode",
        "list_episode_ids",
    ]


def test_execute_load_episode_missing_returns_error(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "ep-9999"},
        config=agent_config,
    )
    assert "error" in result
    assert "ep-9999" in result["error"]


def test_list_episode_ids_includes_listened_flag(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "400", "limit": 5},
        config=agent_config,
    )
    ep400 = next(e for e in result["episodes"] if e["episode_id"] == "ep-0400")
    assert ep400["listened"] is False


def test_load_episode_bare_number_resolves(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "191"},
        config=agent_config,
    )
    assert "error" not in result
    assert result["episode_id"] == "ep-0191"


def test_list_episode_ids_bare_number_top_score(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "191", "limit": 3},
        config=agent_config,
    )
    assert result["episodes"]
    assert result["episodes"][0]["episode_id"] == "ep-0191"
    assert result["episodes"][0]["score"] == 1.0


def test_list_episode_ids_naval_includes_ep_0191(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "Naval Ravikant", "limit": 3},
        config=agent_config,
    )
    ids = [e["episode_id"] for e in result["episodes"]]
    assert "ep-0191" in ids


def test_list_episode_ids_no_regex_on_episode_phrase(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "episode 191", "limit": 5},
        config=agent_config,
    )
    top = result["episodes"][0] if result["episodes"] else None
    assert top is None or top.get("score", 0) < 1.0


def test_resolve_episode_ref_ambiguous_henry_ford(agent_config: AgentConfig):
    del agent_config  # fixture sets VAULT_ROOT
    from vault import resolve_episode_ref

    assert resolve_episode_ref("Henry Ford") is None


def test_load_episode_ambiguous_guest_errors(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "Henry Ford"},
        config=agent_config,
    )
    assert "error" in result
    assert isinstance(result.get("candidates"), list)
    assert len(result["candidates"]) > 0


def _fake_tool_call(name: str, arguments: dict, *, call_id: str = "call_1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


def _fake_response(*, content: str | None = None, tool_calls: list | None = None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _stream_from_response(response: SimpleNamespace, *, delay_s: float = 0.0, usage_tokens: int = 0):
    """Simulate a one-chunk stream for agentic loop tests."""
    import time

    msg = response.choices[0].message
    delta = SimpleNamespace(
        content=msg.content,
        tool_calls=None,
    )
    if msg.tool_calls:
        delta.tool_calls = [
            SimpleNamespace(
                index=i,
                id=tc.id,
                function=SimpleNamespace(
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ),
            )
            for i, tc in enumerate(msg.tool_calls)
        ]

    def _gen():
        if delay_s:
            time.sleep(delay_s)
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=delta)])
        if usage_tokens:
            chunk.usage = SimpleNamespace(completion_tokens=usage_tokens)
        yield chunk

    return _gen()


def test_tool_status_label_known_tools():
    assert tool_status_label("search_vault") == "Searching vault…"
    assert tool_status_label("search_vault_many") == "Searching vault (parallel)…"
    assert tool_status_label("load_episode") == "Loading episode…"
    assert tool_status_label("unknown_tool") == "Searching vault…"


def test_run_turn_cold_start_no_tools(agent_config: AgentConfig):
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _stream_from_response(_fake_response(content="Hello! How can I help?"))

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn("hello", completion_fn=fake_completion)

    assert not result.error
    assert "hello" in result.content.lower() or "help" in result.content.lower()
    assert result.stop_reason == "natural"
    assert "tools" in calls[0]
    assert "search_vault" in [t["function"]["name"] for t in calls[0]["tools"]]
    assert not any(t.get("tool") == "retrieval_orchestrator" for t in result.tool_trace)


def test_run_turn_search_vault_tool_trace(agent_config: AgentConfig, monkeypatch: pytest.MonkeyPatch):
    from search_turn import search_vault_for_turn

    monkeypatch.setattr(
        "search_turn.search_vault_for_turn",
        lambda query, **kwargs: {
            "query": query,
            "evidence": "### Evidence\nQuote: discipline [ep-0016]",
            "meta": {"intent": "thematic"},
            "trace_evidence": [
                {"episode_id": "ep-0016", "rerank_score": 8.0, "chunk_id": "c1"},
            ],
        },
    )

    step = 0

    def fake_completion(**kwargs):
        nonlocal step
        step += 1
        if step == 1:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[_fake_tool_call("search_vault", {"query": "Rockefeller discipline"})],
                )
            )
        return _stream_from_response(
            _fake_response(content="Rockefeller valued discipline [ep-0016].")
        )

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn("What did Rockefeller believe about discipline?", completion_fn=fake_completion)

    assert not result.error
    assert "ep-0016" in result.content
    assert any(t.get("tool") == "search_vault" for t in result.tool_trace)
    assert result.trace_summary
    assert "stop: natural" in result.trace_summary


def test_run_turn_search_vault_many_labels_subqueries(agent_config: AgentConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "search_turn.search_vault_many_for_turn",
        lambda queries, **kwargs: {
            "results": [
                {
                    "query": q,
                    "evidence": f"### {q}\nEvidence for {q}",
                    "trace_evidence": [{"episode_id": "ep-0001", "rerank_score": 7.0}],
                }
                for q in queries
            ],
        },
    )

    step = 0

    def fake_completion(**kwargs):
        nonlocal step
        step += 1
        if step == 1:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[
                        _fake_tool_call(
                            "search_vault_many",
                            {
                                "queries": [
                                    "how Edison built teams",
                                    "how Rockefeller built teams",
                                ],
                            },
                        )
                    ],
                )
            )
        return _stream_from_response(
            _fake_response(content="Edison and Rockefeller differed on teams [ep-0001].")
        )

    result = VaultAgent(config=agent_config).run_turn(
        "How did Edison and Rockefeller differ in building teams?",
        completion_fn=fake_completion,
    )
    assert not result.error
    assert any(t.get("tool") == "search_vault_many" for t in result.tool_trace)
    round_entries = [t for t in result.tool_trace if t.get("record") == "round" and t.get("tools")]
    assert len(round_entries) == 1
    assert len(round_entries[0]["queries"]) == 2


def test_run_turn_cap_forces_final_answer(agent_config: AgentConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "search_turn.search_vault_for_turn",
        lambda query, **kwargs: {
            "query": query,
            "evidence": "thin evidence",
            "meta": {},
            "trace_evidence": [
                {"episode_id": "ep-0016", "rerank_score": 7.0},
                {"episode_id": "ep-0043", "rerank_score": 6.5},
            ],
        },
    )

    cap_messages: list[list[dict[str, str]]] = []

    def fake_completion(**kwargs):
        if kwargs.get("tool_choice") == "none":
            cap_messages.append(kwargs.get("messages") or [])
            return _stream_from_response(
                _fake_response(
                    content="The vault has limited coverage here; best I can say is thin [ep-0016].",
                )
            )
        return _stream_from_response(
            _fake_response(
                tool_calls=[_fake_tool_call("search_vault", {"query": "more please"})],
            )
        )

    result = VaultAgent(config=agent_config).run_turn(
        "obscure topic",
        completion_fn=fake_completion,
    )
    assert result.stop_reason == "cap"
    assert "thin" in result.content.lower() or "limited" in result.content.lower()
    tool_rounds = [t for t in result.tool_trace if t.get("record") == "round" and t.get("tools")]
    assert len(tool_rounds) == MAX_TOOL_ROUNDS
    assert cap_messages
    system_msgs = [m for m in cap_messages[0] if m.get("role") == "system"]
    nudge = system_msgs[-1]["content"]
    assert "Evidence gathered:" in nudge
    assert "ep-0016" in nudge
    assert "ep-0043" in nudge


def test_run_turn_cap_dsml_only_uses_thin_fallback(
    agent_config: AgentConfig, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "search_turn.search_vault_for_turn",
        lambda query, **kwargs: {
            "query": query,
            "evidence": "thin evidence",
            "meta": {},
            "trace_evidence": [
                {"episode_id": "ep-0016", "rerank_score": 7.0},
            ],
        },
    )

    dsml_only = '<DSML invoke="x">only markup</DSML>'

    def fake_completion(**kwargs):
        if kwargs.get("tool_choice") == "none":
            return _stream_from_response(_fake_response(content=dsml_only))
        return _stream_from_response(
            _fake_response(
                tool_calls=[_fake_tool_call("search_vault", {"query": "more please"})],
            )
        )

    result = VaultAgent(config=agent_config).run_turn(
        "obscure topic",
        completion_fn=fake_completion,
    )
    assert result.stop_reason == "cap"
    assert result.content != EMPTY_SYNTHESIS
    assert "ep-0016" in result.content
    assert "DSML" not in result.content


def test_search_budget_nudge_summarizes_trace_evidence():
    nudge = _search_budget_nudge(
        [
            {"episode_id": "ep-0001"},
            {"episode_id": "ep-0002"},
            {"episode_id": "ep-0001"},
        ]
    )
    assert "ep-0001" in nudge
    assert "ep-0002" in nudge
    assert "(3 chunks)" in nudge


def test_build_trace_summary_includes_rounds():
    trace = [
        {
            "record": "round",
            "round": 1,
            "tools": ["search_vault"],
            "queries": ["Rockefeller"],
            "evidence": [{"episode_id": "ep-0016", "rerank_score": 8.0}],
        },
        {
            "record": "round",
            "round": 2,
            "tools": [],
            "queries": [],
            "evidence": [],
        },
    ]
    summary = build_trace_summary(trace, stop_reason="natural")
    assert "round 1: search_vault" in summary
    assert "ep-0016" in summary


def test_run_turn_on_tool_start_callback(agent_config: AgentConfig):
    seen: list[str] = []

    def fake_completion(**kwargs):
        if kwargs.get("tool_choice") == "auto" and seen == []:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[_fake_tool_call("list_episode_ids", {"query": "191"})],
                )
            )
        return _stream_from_response(_fake_response(content="Episode 191 is Naval [ep-0191]."))

    agent = VaultAgent(config=agent_config)
    agent.run_turn(
        "episode 191",
        completion_fn=fake_completion,
        on_tool_start=lambda name, _args: seen.append(name),
    )
    assert "list_episode_ids" in seen


def test_run_turn_load_episode_via_tools(agent_config: AgentConfig):
    step = 0

    def fake_completion(**kwargs):
        nonlocal step
        step += 1
        if step == 1:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[_fake_tool_call("load_episode", {"episode_id": "ep-0016"})],
                )
            )
        return _stream_from_response(_fake_response(content="Full episode payload [ep-0016]."))

    result = VaultAgent(config=agent_config).run_turn(
        "Load episode ep-0016.",
        completion_fn=fake_completion,
    )
    assert not result.error
    assert any(t.get("tool") == "load_episode" for t in result.tool_trace)


def test_run_turn_stream_timing(agent_config: AgentConfig):
    import time

    from turn_timing import TurnTimer

    timer = TurnTimer()
    content = "Timed answer with enough tokens here for rate calculation."

    def fake_completion(**kwargs):
        def _gen():
            time.sleep(0.03)
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="Timed ", tool_calls=None))]
            )
            time.sleep(0.05)
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=content[len("Timed ") :], tool_calls=None)
                    )
                ],
                usage=SimpleNamespace(completion_tokens=40),
            )

        return _gen()

    result = VaultAgent(config=agent_config).run_turn(
        "hello",
        completion_fn=fake_completion,
        timing=timer,
    )
    assert not result.error
    assert result.timing is not None
    assert result.timing.get("agent_ttft_ms_mean") is not None
    assert result.timing.get("generation_tok_per_sec_mean") is not None
    calls = result.timing.get("openrouter_calls") or []
    assert calls
    assert calls[0]["label"] == "agent_round_1"
    assert calls[0]["tok_per_sec"] is not None
    assert any(t.get("record") == "timing" for t in result.tool_trace)


def test_run_turn_emits_spans_with_telemetry(agent_config: AgentConfig):
    from telemetry import TurnTimerCollector
    from turn_timing import TurnTimer

    timer = TurnTimer()
    telemetry = TurnTimerCollector()

    def fake_completion(**kwargs):
        return _stream_from_response(_fake_response(content="Direct answer [ep-0016]."))

    result = VaultAgent(config=agent_config).run_turn(
        "hello",
        completion_fn=fake_completion,
        timing=timer,
        telemetry=telemetry,
    )
    assert not result.error
    spans_record = next(t for t in result.tool_trace if t.get("record") == "spans")
    span_names = [s["name"] for s in spans_record.get("spans") or []]
    assert "agent.synthesis.final" in span_names
    calls = (result.timing or {}).get("openrouter_calls") or []
    assert calls
    assert calls[0].get("span_name") == "agent.synthesis.final"
