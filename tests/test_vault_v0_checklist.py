"""v0 success criteria for the Telegram vault agent (automated subset). See docs/testing.md."""

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


def _stream_from_response(response: SimpleNamespace):
    msg = response.choices[0].message
    delta = SimpleNamespace(content=msg.content, tool_calls=None)
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
    yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def test_v0_criterion_retrieval_in_trace(agent_config: AgentConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "search_turn.search_vault_for_turn",
        lambda query, **kwargs: {
            "query": query,
            "evidence": "Quote: discipline [ep-0016]",
            "meta": {},
            "trace_evidence": [{"episode_id": "ep-0016", "rerank_score": 8.0}],
        },
    )

    calls: list[dict] = []
    step = 0

    def fake_completion(**kwargs):
        calls.append(kwargs)
        nonlocal step
        step += 1
        if step == 1:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[_fake_tool_call("search_vault", {"query": "Rockefeller discipline"})],
                )
            )
        return _stream_from_response(_fake_response(content="Discipline [ep-0016]."))

    agent = VaultAgent(config=agent_config)
    result = agent.run_turn(
        "Rockefeller discipline",
        completion_fn=fake_completion,
    )
    assert any(t.get("tool") == "search_vault" for t in result.tool_trace)
    if calls and "tools" in calls[0]:
        assert "web_search" not in [t["function"]["name"] for t in calls[0]["tools"]]


def test_v0_criterion_expanded_in_index(agent_config: AgentConfig):
    _ = agent_config
    if os.getenv("RUN_REBUILT_INDEX_SCENARIOS") != "1":
        pytest.skip("expanded index check requires RUN_REBUILT_INDEX_SCENARIOS=1")
    from vault import search_vault_parent

    result = search_vault_parent("inner scorecard Buffett", k=5)
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
    _ = agent_config
    from vault import search_transcript, search_vault_parent

    for name, fn in (
        ("search_vault_parent", search_vault_parent),
        ("search_transcript", search_transcript),
    ):
        result = fn("Naval Ravikant wealth happiness", k=8)
        unlistened = [h for h in (result.get("hits") or []) if h.get("episode_id") == "ep-0400"]
        assert len(unlistened) == 0, f"{name} returned ep-0400 hits: {unlistened[:2]}"


def test_v0_criterion_unlistened_load_episode(agent_config: AgentConfig):
    result = execute_tool(
        "load_episode",
        {"episode_id": "ep-0400"},
        config=agent_config,
    )
    assert result["meta"]["listened"] is False
    assert not (result.get("sections") or {}).get("expanded")


def test_v0_criterion_unlistened_agent_response(agent_config: AgentConfig):
    step = 0

    def fake_completion(**kwargs):
        nonlocal step
        step += 1
        if step == 1:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[_fake_tool_call("list_episode_ids", {"query": "James Dyson"})],
                )
            )
        if step == 2:
            return _stream_from_response(
                _fake_response(
                    tool_calls=[_fake_tool_call("load_episode", {"episode_id": "ep-0400"})],
                )
            )
        return _stream_from_response(
            _fake_response(
                content="You have not studied ep-0400 yet — only the transcript exists until you add timestamp bullets.",
            )
        )

    result = VaultAgent(config=agent_config).run_turn(
        "What did I note about James Dyson?",
        completion_fn=fake_completion,
    )
    lowered = result.content.lower()
    assert "studied" in lowered or "not listened" in lowered or "ep-0400" in lowered
