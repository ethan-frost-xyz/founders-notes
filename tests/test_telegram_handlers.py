"""Telegram librarian handler tests (mocked VaultAgent, no live Bot API)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("telegram")

REPO = Path(__file__).resolve().parent.parent

from agent import TurnResult  # noqa: E402
from handlers import on_text  # noqa: E402
from telegram_test_helpers import make_bot_config, make_context, text_update  # noqa: E402


@pytest.fixture
def bot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "BotConfig":
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    return make_bot_config(REPO, tmp_path)


def _run(coro):
    return asyncio.run(coro)


def test_on_text_unauthorized(bot_config, tmp_path: Path):
    update = text_update("Rockefeller discipline", user_id=999)
    context = make_context(bot_config, agent=MagicMock())
    _run(on_text(update, context))  # type: ignore[arg-type]
    update.message.reply_text.assert_awaited_once_with("Unauthorized.")


def test_on_text_runs_agent_and_persists_turn(bot_config):
    agent = MagicMock()
    agent.run_turn.return_value = TurnResult(
        content="Answer about discipline [ep-0016].",
        tool_trace=[{"tool": "search_vault", "query": "rockefeller discipline"}],
    )
    context = make_context(bot_config, agent=agent)
    update = text_update("How did Rockefeller think about discipline?")

    with patch("librarian_turn.effective_stream_replies", return_value=(False, "off")):
        _run(on_text(update, context))  # type: ignore[arg-type]

    agent.run_turn.assert_called_once()
    call_kw = agent.run_turn.call_args.kwargs
    assert call_kw.get("on_chunk") is None
    uid = update.effective_user.id
    messages = context.application.bot_data["sessions"].get(uid).messages
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert "ep-0016" in messages[1].content
    update.message.reply_chat_action.assert_awaited_once_with("typing")


def test_on_text_streaming_passes_on_chunk(bot_config):
    agent = MagicMock()
    agent.run_turn.return_value = TurnResult(content="Streamed answer.")
    context = make_context(bot_config, agent=agent)
    update = text_update("Tell me about Buffett")

    with patch("librarian_turn.effective_stream_replies", return_value=(True, "on")):
        _run(on_text(update, context))  # type: ignore[arg-type]

    assert agent.run_turn.call_args.kwargs.get("on_chunk") is not None


def test_on_text_tool_status_scheduled(bot_config):
    agent = MagicMock()
    captured: dict = {}

    def fake_run_turn(*_args, on_tool_start=None, **_kwargs):
        if on_tool_start:
            on_tool_start("search_vault", {"query": "test"})
        return TurnResult(content="Done.")

    agent.run_turn.side_effect = fake_run_turn
    context = make_context(bot_config, agent=agent)
    update = text_update("theme question")

    with patch("librarian_turn.effective_stream_replies", return_value=(False, "off")):
        _run(on_text(update, context))  # type: ignore[arg-type]

    assert update.message.reply_text.await_count >= 1


def test_on_text_timing_jsonl_when_enabled(bot_config, monkeypatch: pytest.MonkeyPatch):
    agent = MagicMock()
    agent.run_turn.return_value = TurnResult(
        content="Timed.",
        timing={"openrouter_calls": []},
    )
    context = make_context(bot_config, agent=agent)
    update = text_update("timing test")

    with (
        patch("librarian_turn.effective_stream_replies", return_value=(False, "off")),
        patch("librarian_turn.is_timing_enabled", return_value=True),
        patch("librarian_turn.append_timing_jsonl") as mock_append,
    ):
        _run(on_text(update, context))  # type: ignore[arg-type]

    mock_append.assert_called_once()


def test_on_text_delegates_to_janitor_when_active(bot_config):
    agent = MagicMock()
    context = make_context(bot_config, agent=agent)
    uid = 111
    janitor = context.application.bot_data["janitor"]
    from janitor_store import JanitorPhase

    session = janitor.get(uid)
    session.phase = JanitorPhase.AWAIT_EPISODE

    async def _janitor(*_a, **_k):
        return True

    with patch("janitor_handlers.on_janitor_text", side_effect=_janitor):
        update = text_update("191")
        _run(on_text(update, context))  # type: ignore[arg-type]

    agent.run_turn.assert_not_called()
