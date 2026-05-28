"""SP2 vault agent: tool wiring and mock OpenRouter contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent

from agent import (  # noqa: E402
    VaultAgent,
    execute_tool,
    openrouter_tools,
    web_search_stub,
)
from config import AgentConfig  # noqa: E402


@pytest.fixture
def agent_config(monkeypatch: pytest.MonkeyPatch) -> AgentConfig:
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    return AgentConfig(
        api_key="test-key",
        model="test/model",
        vault_root=REPO,
        max_steps=5,
    )


def test_openrouter_tools_excludes_web_by_default():
    names = [t["function"]["name"] for t in openrouter_tools(allow_web=False)]
    assert "search_vault_parent" in names
    assert "web_search" not in names


def test_openrouter_tools_includes_web_when_allowed():
    names = [t["function"]["name"] for t in openrouter_tools(allow_web=True)]
    assert "web_search" in names


def test_web_search_stub_not_configured():
    assert web_search_stub("test query") == {"error": "not configured", "query": "test query"}


def test_execute_search_vault_parent_evidence_shape(agent_config: AgentConfig):
    result = execute_tool(
        "search_vault_parent",
        {"query": "Rockefeller", "k": 2},
        config=agent_config,
        allow_web=False,
    )
    assert "hits" in result
    assert "meta" in result
    assert result["meta"]["tier"] == "parent"
    if result["hits"]:
        hit = result["hits"][0]
        assert "chunk_id" in hit
        assert "episode_id" in hit
        assert "excerpt" in hit


def test_execute_web_blocked_when_allow_web_false(agent_config: AgentConfig):
    result = execute_tool(
        "web_search",
        {"query": "news"},
        config=agent_config,
        allow_web=False,
    )
    assert result.get("error") == "web_search disabled for this turn"


def test_execute_load_episode_missing_returns_error(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "ep-9999"},
        config=agent_config,
        allow_web=False,
    )
    assert "error" in result
    assert "ep-9999" in result["error"]


def test_load_episode_unlistened_ep_0400(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "ep-0400"},
        config=agent_config,
        allow_web=False,
    )
    assert result["episode_id"] == "ep-0400"
    assert result["meta"]["listened"] is False
    assert "expanded" not in result.get("sections", {})


def test_list_episode_ids_includes_listened_flag(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "400", "limit": 5},
        config=agent_config,
        allow_web=False,
    )
    ep400 = next(e for e in result["episodes"] if e["episode_id"] == "ep-0400")
    assert ep400["listened"] is False


def test_load_episode_bare_number_resolves(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "191"},
        config=agent_config,
        allow_web=False,
    )
    assert "error" not in result
    assert result["episode_id"] == "ep-0191"


def test_list_episode_ids_bare_number_top_score(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "191", "limit": 3},
        config=agent_config,
        allow_web=False,
    )
    assert result["episodes"]
    assert result["episodes"][0]["episode_id"] == "ep-0191"
    assert result["episodes"][0]["score"] == 1.0


def test_list_episode_ids_naval_includes_ep_0191(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "Naval Ravikant", "limit": 3},
        config=agent_config,
        allow_web=False,
    )
    ids = [e["episode_id"] for e in result["episodes"]]
    assert "ep-0191" in ids


def test_list_episode_ids_no_regex_on_episode_phrase(agent_config: AgentConfig):
    result = execute_tool(
        "list_episode_ids",
        {"query": "episode 191", "limit": 5},
        config=agent_config,
        allow_web=False,
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
        allow_web=False,
    )
    assert "error" in result


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


def test_run_turn_traces_search_vault_parent(agent_config: AgentConfig):
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _fake_response(
                tool_calls=[
                    _fake_tool_call("search_vault_parent", {"query": "Rockefeller discipline"}),
                ],
            )
        return _fake_response(content="Rockefeller valued discipline [ep-0016].")

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn(
        "What did Rockefeller believe about discipline?",
        completion_fn=fake_completion,
    )

    assert "Rockefeller" in result.content
    assert not result.error
    assert any(t["tool"] == "search_vault_parent" for t in result.tool_trace)
    tool_names = [t["function"]["name"] for t in calls[0]["tools"]]
    assert "web_search" not in tool_names


def test_run_turn_never_registers_web_search_when_disabled(agent_config: AgentConfig):
    def fake_completion(**kwargs):
        tool_names = [t["function"]["name"] for t in kwargs["tools"]]
        assert "web_search" not in tool_names
        return _fake_response(content="Done.")

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn("Hello", completion_fn=fake_completion, allow_web=False)
    assert result.content == "Done."
    assert not any(t["tool"] == "web_search" for t in result.tool_trace)


def test_run_turn_forces_final_answer_on_last_step(agent_config: AgentConfig):
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if kwargs.get("tool_choice") == "none":
            return _fake_response(content="Buffett inner scorecard [ep-0100].")
        return _fake_response(
            tool_calls=[
                _fake_tool_call(
                    "search_vault_parent",
                    {"query": "inner scorecard"},
                    call_id=f"call_{len(calls)}",
                ),
            ],
        )

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn(
        "What did Buffett mean by inner scorecard?",
        completion_fn=fake_completion,
    )

    assert not result.error
    assert "ep-0100" in result.content
    assert calls[-1].get("tool_choice") == "none"


def test_run_turn_final_step_ignores_tool_calls(agent_config: AgentConfig):
    def fake_completion(**kwargs):
        if kwargs.get("tool_choice") == "none":
            return _fake_response(
                tool_calls=[_fake_tool_call("search_vault_parent", {"query": "naval"})],
                content="You have not studied ep-0191 yet.",
            )
        return _fake_response(
            tool_calls=[
                _fake_tool_call("list_episode_ids", {"query": "Naval"}, call_id="c1"),
            ],
        )

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn("What about Naval ep 191?", completion_fn=fake_completion)

    assert not result.error
    assert "ep-0191" in result.content or "studied" in result.content.lower()
    assert "step limit" not in result.content.lower()


def test_run_turn_allows_web_tool_registration(agent_config: AgentConfig):
    seen_web = False

    def fake_completion(**kwargs):
        nonlocal seen_web
        tool_names = [t["function"]["name"] for t in kwargs["tools"]]
        seen_web = "web_search" in tool_names
        if len(kwargs["messages"]) <= 2:
            return _fake_response(
                tool_calls=[_fake_tool_call("web_search", {"query": "weather"})],
            )
        return _fake_response(content="External info unavailable.")

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn("What's the weather?", completion_fn=fake_completion, allow_web=True)

    assert seen_web
    assert any(t["tool"] == "web_search" for t in result.tool_trace)
    assert "unavailable" in result.content.lower() or "not configured" in str(result.tool_trace)
