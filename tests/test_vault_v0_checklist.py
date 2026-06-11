"""v0 success criteria for the Telegram vault agent (automated subset). See docs/testing.md."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent

from agent import VaultAgent, execute_tool  # noqa: E402
from config import AgentConfig  # noqa: E402


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


def test_v0_criterion_expanded_in_index(agent_config: AgentConfig):
    _ = agent_config
    if os.getenv("RUN_REBUILT_INDEX_SCENARIOS") != "1":
        pytest.skip("expanded index check requires RUN_REBUILT_INDEX_SCENARIOS=1")
    from search_test_helpers import run_parent_search

    result = run_parent_search("inner scorecard Buffett", k=5, vault_root=agent_config.vault_root)
    hits = result.get("hits") or []
    assert hits
    assert any((h.get("section") or "").startswith("expanded:") for h in hits)


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
