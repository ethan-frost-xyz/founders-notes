"""v0 success criteria from telegram_rag_bot_v0.plan.md (automated subset)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent

from agent import VaultAgent, execute_tool  # noqa: E402
from auth import is_allowed  # noqa: E402
from config import AgentConfig, BotConfig  # noqa: E402
from sessions import SessionStore  # noqa: E402


@pytest.fixture
def agent_config(monkeypatch: pytest.MonkeyPatch) -> AgentConfig:
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    return AgentConfig(
        api_key="test-key",
        model="test/model",
        vault_root=REPO,
        max_steps=5,
    )


@pytest.fixture
def bot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BotConfig:
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    agent = AgentConfig(api_key="k", model="m", vault_root=REPO)
    sessions_dir = tmp_path / "telegram-sessions"
    sessions_dir.mkdir()
    return BotConfig(
        agent=agent,
        telegram_token="t",
        allowed_user_ids=frozenset({111}),
        sessions_dir=sessions_dir,
    )


def _fake_tool_call(name: str, arguments: dict, *, call_id: str = "c1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _fake_response(*, content: str | None = None, tool_calls: list | None = None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=content, tool_calls=tool_calls,
    ))])


def test_v0_criterion_search_parent_in_trace(agent_config: AgentConfig):
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _fake_response(
                tool_calls=[_fake_tool_call("search_vault_parent", {"query": "Rockefeller"})],
            )
        return _fake_response(content="Discipline [ep-0016].")

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn("Rockefeller discipline", completion_fn=fake_completion)
    assert any(t["tool"] == "search_vault_parent" for t in result.tool_trace)
    assert "web_search" not in [t["function"]["name"] for t in calls[0]["tools"]]


def test_v0_criterion_web_gated(agent_config: AgentConfig):
    def fake_completion(**kwargs):
        names = [t["function"]["name"] for t in kwargs["tools"]]
        assert "web_search" not in names
        return _fake_response(content="Vault only.")

    VaultAgent(config=agent_config).run_turn(
        "hello", completion_fn=fake_completion, allow_web=False,
    )

    web_seen = False

    def fake_web(**kwargs):
        nonlocal web_seen
        web_seen = "web_search" in [t["function"]["name"] for t in kwargs["tools"]]
        return _fake_response(
            tool_calls=[_fake_tool_call("web_search", {"query": "x"})],
        )

    VaultAgent(config=agent_config).run_turn(
        "weather", completion_fn=fake_web, allow_web=True,
    )
    assert web_seen


def test_v0_criterion_expanded_in_index(agent_config: AgentConfig):
    if os.getenv("RUN_REBUILT_INDEX_SCENARIOS") != "1":
        pytest.skip("expanded index check requires RUN_REBUILT_INDEX_SCENARIOS=1")
    result = execute_tool(
        "search_vault_parent",
        {"query": "inner scorecard Buffett", "k": 5},
        config=agent_config,
        allow_web=False,
    )
    hits = result.get("hits") or []
    assert hits
    assert any((h.get("section") or "").startswith("expanded:") for h in hits)


def test_v0_criterion_allowlist(bot_config: BotConfig):
    assert is_allowed(111, bot_config)
    assert not is_allowed(999, bot_config)


def test_v0_criterion_newchat_export(bot_config: BotConfig):
    store = SessionStore(bot_config)
    uid = 111
    store.append_turn(uid, user_text="Q", assistant_text="A [ep-0100].")
    path = store.new_chat(uid)
    assert path is not None
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines[0]["record"] == "meta"
    assert any(r.get("role") == "user" for r in lines if r.get("record") == "message")


def test_v0_criterion_unlistened_no_hits(agent_config: AgentConfig):
    for tool in ("search_vault_parent", "search_transcript"):
        result = execute_tool(
            tool,
            {"query": "Naval Ravikant wealth happiness", "k": 8},
            config=agent_config,
            allow_web=False,
        )
        unlistened = [h for h in (result.get("hits") or []) if h.get("episode_id") == "ep-0400"]
        assert len(unlistened) == 0, f"{tool} returned ep-0400 hits: {unlistened[:2]}"


def test_v0_criterion_unlistened_load_episode(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "ep-0400"},
        config=agent_config,
        allow_web=False,
    )
    assert result["meta"]["listened"] is False
    assert not (result.get("sections") or {}).get("expanded")


def test_v0_criterion_unlistened_agent_response(agent_config: AgentConfig):
    calls: list[dict] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _fake_response(
                tool_calls=[_fake_tool_call("list_episode_ids", {"query": "Naval Ravikant"})],
            )
        if len(calls) == 2:
            return _fake_response(
                tool_calls=[_fake_tool_call("load_episode", {"episode_id": "ep-0191"})],
            )
        return _fake_response(
            content="You have not studied ep-0191 yet — only the transcript exists until you add timestamp bullets.",
        )

    result = VaultAgent(config=agent_config).run_turn(
        "What did I note about Naval Ravikant?",
        completion_fn=fake_completion,
        allow_web=False,
    )
    assert "search_transcript" not in [t["tool"] for t in result.tool_trace]
    lowered = result.content.lower()
    assert "studied" in lowered or "not listened" in lowered or "ep-0191" in lowered
