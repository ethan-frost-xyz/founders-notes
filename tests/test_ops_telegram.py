"""Async ops job wrappers for Telegram commands and settings panel."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("telegram")

REPO = Path(__file__).resolve().parent.parent

from ops_telegram import run_ops_job, run_ops_job_edit  # noqa: E402
from telegram_test_helpers import MockMessage  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_run_ops_job_lock_busy():
    message = MockMessage()
    bot_data: dict = {}

    with (
        patch("ops_runner.ops_lock_held", return_value=True),
        patch("ops_runner.try_acquire_ops_lock", return_value=False),
    ):
        _run(
            run_ops_job(
                message,  # type: ignore[arg-type]
                bot_data,
                REPO,
                label="git pull",
                fn=lambda _p: (0, "ok"),
            )
        )

    message.reply_text.assert_awaited_once_with(
        "Another op is already running. Try again later."
    )


def test_run_ops_job_success():
    message = MockMessage()
    bot_data: dict = {}

    def fake_pull(_vault: Path) -> tuple[int, str]:
        return 0, "Already up to date."

    with (
        patch("ops_runner.ops_lock_held", return_value=False),
        patch("ops_runner.try_acquire_ops_lock", return_value=True),
        patch("ops_runner.release_ops_lock"),
        patch("messaging.reply_text_chunked", new_callable=AsyncMock) as mock_chunk,
    ):
        _run(
            run_ops_job(
                message,  # type: ignore[arg-type]
                bot_data,
                REPO,
                label="git pull",
                fn=fake_pull,
                started="Pull started.",
            )
        )

    assert message.reply_text.await_count == 1
    mock_chunk.assert_awaited_once()
    body = mock_chunk.await_args[0][1]
    assert "Done" in body
    assert "git pull" in body


def test_run_ops_job_failure():
    message = MockMessage()
    bot_data: dict = {}

    def fail_op(_vault: Path) -> tuple[int, str]:
        return 1, "chunk build failed"

    with (
        patch("ops_runner.ops_lock_held", return_value=False),
        patch("ops_runner.try_acquire_ops_lock", return_value=True),
        patch("ops_runner.release_ops_lock"),
        patch("messaging.reply_text_chunked", new_callable=AsyncMock) as mock_chunk,
    ):
        _run(
            run_ops_job(
                message,  # type: ignore[arg-type]
                bot_data,
                REPO,
                label="reindex",
                fn=fail_op,
            )
        )

    body = mock_chunk.await_args[0][1]
    assert "Failed (exit 1)" in body
    assert "chunk build failed" in body


def test_run_ops_job_edit_lock_busy():
    message = MockMessage()

    with (
        patch("ops_runner.ops_lock_held", return_value=True),
        patch("ops_runner.try_acquire_ops_lock", return_value=False),
    ):
        _run(
            run_ops_job_edit(
                message,  # type: ignore[arg-type]
                {},
                REPO,
                label="sync",
                fn=lambda _p: (0, "ok"),
                running_text="Sync running…",
            )
        )

    message.edit_text.assert_awaited_once()
    assert "already running" in message.edit_text.await_args[0][0].lower()


def test_run_ops_job_edit_success():
    message = MockMessage()
    bot_data: dict = {}

    with (
        patch("ops_runner.ops_lock_held", return_value=False),
        patch("ops_runner.try_acquire_ops_lock", return_value=True),
        patch("ops_runner.release_ops_lock"),
    ):
        _run(
            run_ops_job_edit(
                message,  # type: ignore[arg-type]
                bot_data,
                REPO,
                label="git pull",
                fn=lambda _p: (0, "pulled"),
                running_text="Pull running…",
            )
        )

    final_call = message.edit_text.await_args_list[-1]
    assert "Done" in final_call[0][0]
    assert "pulled" in final_call[0][0]
