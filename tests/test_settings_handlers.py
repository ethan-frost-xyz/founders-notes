"""Settings tap UI: presets, callback_data length, and callback dispatch."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("telegram")

REPO = Path(__file__).resolve().parent.parent

from model_presets import MODEL_PRESETS, ROLE_LABELS  # noqa: E402
from settings_handlers import (  # noqa: E402
    _janitor_temp_keyboard,
    _ops_keyboard,
    _role_preset_keyboard,
    on_settings_callback,
    settings_keyboard,
)
from telegram_test_helpers import callback_update, make_bot_config, make_context  # noqa: E402
from ui_keyboards import BACK_LABEL  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def bot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "111")
    runtime = tmp_path / "runtime.json"
    runtime.write_text('{"librarian_model": "rt/librarian"}\n', encoding="utf-8")
    monkeypatch.setenv("FOUNDERS_TELEGRAM_RUNTIME", str(runtime))
    return make_bot_config(REPO, tmp_path)


def test_callback_data_under_telegram_limit():
    for role in ROLE_LABELS:
        for idx in range(len(MODEL_PRESETS.get(role, []))):
            data = f"set:p:{role}:{idx}"
            assert len(data.encode("utf-8")) <= 64, data
    kb = settings_keyboard()
    for row in kb.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64, btn.callback_data


def test_role_keyboard_has_presets_and_back():
    kb = _role_preset_keyboard("librarian")
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "mimo-v2.5-pro" in labels
    assert BACK_LABEL in labels
    assert "Type custom slug…" in labels


def test_janitor_temp_keyboard_presets():
    kb = _janitor_temp_keyboard()
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "0.2" in labels
    assert BACK_LABEL in labels


def test_all_settings_submenus_have_back():
    for kb in (
        _ops_keyboard(),
        _role_preset_keyboard("librarian"),
        _janitor_temp_keyboard(),
    ):
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        assert BACK_LABEL in labels


def test_settings_stream_toggle(bot_config):
    context = make_context(bot_config)
    update = callback_update("set:stream")

    with patch("settings_handlers.effective_stream_replies", return_value=(False, "off")):
        _run(on_settings_callback(update, context))  # type: ignore[arg-type]

    update.callback_query.message.edit_text.assert_awaited()
    body = update.callback_query.message.edit_text.await_args[0][0]
    assert "Stream replies turned on" in body


def test_settings_ops_panel(bot_config):
    context = make_context(bot_config)
    update = callback_update("set:ops")
    _run(on_settings_callback(update, context))  # type: ignore[arg-type]
    update.callback_query.message.edit_text.assert_awaited_once()
    assert "Vault ops" in update.callback_query.message.edit_text.await_args[0][0]


def test_settings_model_preset_applies(bot_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime = tmp_path / "runtime.json"
    runtime.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("FOUNDERS_TELEGRAM_RUNTIME", str(runtime))
    context = make_context(bot_config)
    update = callback_update("set:p:librarian:0")
    _run(on_settings_callback(update, context))  # type: ignore[arg-type]
    body = update.callback_query.message.edit_text.await_args[0][0]
    assert "librarian" in body.lower()


def test_settings_ops_pull_callback(bot_config):
    context = make_context(bot_config)
    update = callback_update("set:op:pull")

    with patch("ops_telegram.run_ops_job_edit", new_callable=AsyncMock) as mock_edit:
        _run(on_settings_callback(update, context))  # type: ignore[arg-type]
        mock_edit.assert_awaited_once()
        assert mock_edit.await_args.kwargs["label"] == "git pull"
