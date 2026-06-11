"""Janitor FSM handler tests with mocked LLM and workflow steps."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("telegram")

REPO = Path(__file__).resolve().parent.parent

from janitor_handlers import (  # noqa: E402
    cmd_janitor,
    cmd_librarian,
    on_janitor_callback,
    on_janitor_text,
)
from janitor_store import JanitorPhase  # noqa: E402
from telegram_test_helpers import (  # noqa: E402
    callback_update,
    make_bot_config,
    make_context,
    text_update,
)

NAVAL_CLEAN = """## Raw datapoints

- 5:00 — Context changes over time
"""


@pytest.fixture
def bot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    return make_bot_config(REPO, tmp_path)


def _run(coro):
    return asyncio.run(coro)


def test_cmd_janitor_enters_await_episode(bot_config):
    context = make_context(bot_config)
    update = text_update("/janitor")
    _run(cmd_janitor(update, context))  # type: ignore[arg-type]
    session = context.application.bot_data["janitor"].get(111)
    assert session.phase == JanitorPhase.AWAIT_EPISODE


def test_cmd_librarian_resets_janitor(bot_config):
    context = make_context(bot_config)
    janitor = context.application.bot_data["janitor"]
    janitor.get(111).phase = JanitorPhase.AWAIT_NOTES
    update = text_update("/librarian")
    _run(cmd_librarian(update, context))  # type: ignore[arg-type]
    assert janitor.get(111).phase == JanitorPhase.IDLE


def test_await_episode_then_notes_flow(bot_config):
    context = make_context(bot_config)
    janitor = context.application.bot_data["janitor"]
    janitor.get(111).phase = JanitorPhase.AWAIT_EPISODE

    update_ep = text_update("191")
    consumed = _run(on_janitor_text(update_ep, context))  # type: ignore[arg-type]
    assert consumed is True
    assert janitor.get(111).episode_id == "ep-0191"
    assert janitor.get(111).phase == JanitorPhase.AWAIT_NOTES

    with patch(
        "janitor_phases.llm_clean_pasted_notes",
        return_value=(NAVAL_CLEAN, []),
    ):
        update_notes = text_update("* bullet one\n* bullet two")
        consumed = _run(on_janitor_text(update_notes, context))  # type: ignore[arg-type]

    assert consumed is True
    assert janitor.get(111).phase == JanitorPhase.PREVIEW
    assert janitor.get(111).cleaned_body == NAVAL_CLEAN


def test_preview_approve_text_shortcut(bot_config):
    context = make_context(bot_config)
    session = context.application.bot_data["janitor"].get(111)
    session.phase = JanitorPhase.PREVIEW
    session.episode_id = "ep-0191"
    session.cleaned_body = NAVAL_CLEAN

    with (
        patch("janitor_phases.needs_overwrite_confirm", return_value=False),
        patch("janitor_phases.file_and_expand", new_callable=AsyncMock) as mock_file,
    ):
        update = text_update("approve")
        consumed = _run(on_janitor_text(update, context))  # type: ignore[arg-type]

    assert consumed is True
    mock_file.assert_awaited_once()


def test_callback_retry_from_preview(bot_config):
    context = make_context(bot_config)
    session = context.application.bot_data["janitor"].get(111)
    session.phase = JanitorPhase.PREVIEW
    session.episode_id = "ep-0191"
    session.raw_paste = "191 naval\n* note"

    with patch(
        "janitor_phases.llm_clean_pasted_notes",
        return_value=(NAVAL_CLEAN, []),
    ):
        update = callback_update("janitor:retry")
        _run(on_janitor_callback(update, context))  # type: ignore[arg-type]

    assert session.phase == JanitorPhase.PREVIEW
    assert session.cleaned_body == NAVAL_CLEAN
    update.callback_query.answer.assert_awaited_once()


def test_callback_promote_stubs_workflow(bot_config):
    context = make_context(bot_config)
    session = context.application.bot_data["janitor"].get(111)
    session.phase = JanitorPhase.REVIEW_DRAFT
    session.episode_id = "ep-0100"

    with (
        patch("janitor_handlers.run_promote", return_value=(0, "promoted", [])),
        patch("janitor_handlers.run_reindex", return_value=(0, "reindexed")),
        patch("janitor_handlers.draft_excerpt", return_value="excerpt"),
    ):
        update = callback_update("janitor:promote")
        _run(on_janitor_callback(update, context))  # type: ignore[arg-type]

    assert context.application.bot_data["janitor"].get(111).phase == JanitorPhase.AWAIT_PUSH
    update.callback_query.message.edit_text.assert_awaited()


def test_callback_push_skip_from_await_push(bot_config):
    context = make_context(bot_config)
    session = context.application.bot_data["janitor"].get(111)
    session.phase = JanitorPhase.AWAIT_PUSH
    session.episode_id = "ep-0100"

    update = callback_update("janitor:push_skip")
    _run(on_janitor_callback(update, context))  # type: ignore[arg-type]

    assert context.application.bot_data["janitor"].get(111).phase == JanitorPhase.IDLE


def test_callback_push_github_success(bot_config):
    context = make_context(bot_config)
    session = context.application.bot_data["janitor"].get(111)
    session.phase = JanitorPhase.AWAIT_PUSH
    session.episode_id = "ep-0100"

    with patch(
        "janitor_handlers.run_vault_push_op",
        return_value=(0, "vault-push: committed and pushed"),
    ):
        update = callback_update("janitor:push")
        _run(on_janitor_callback(update, context))  # type: ignore[arg-type]

    assert context.application.bot_data["janitor"].get(111).phase == JanitorPhase.IDLE
    update.callback_query.message.edit_text.assert_awaited()
