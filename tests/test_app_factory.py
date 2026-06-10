"""Application factory handler registration."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("telegram")

REPO = Path(__file__).resolve().parent.parent

from app_factory import AppOptions, HARNESS_APP_OPTIONS, build_application  # noqa: E402
from telegram_test_helpers import make_bot_config  # noqa: E402


def _handler_commands(app) -> set[str]:
    from telegram.ext import CommandHandler

    names: set[str] = set()
    for group in app.handlers.values():
        for handler in group:
            if isinstance(handler, CommandHandler):
                names.update(handler.commands)
    return names


@pytest.fixture
def bot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VAULT_ROOT", str(REPO))
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "111")
    return make_bot_config(REPO, tmp_path)


def test_production_registers_settings_and_ops(bot_config):
    app = build_application(bot_config=bot_config)
    cmds = _handler_commands(app)
    assert "settings" in cmds
    assert "sync" in cmds
    assert "restart" in cmds


def test_harness_omits_settings_and_ops(bot_config):
    app = build_application(HARNESS_APP_OPTIONS, bot_config=bot_config)
    cmds = _handler_commands(app)
    assert "settings" not in cmds
    assert "sync" not in cmds
    assert "janitor" in cmds
    assert "resume" in cmds


def test_custom_options_disable_settings_only(bot_config):
    app = build_application(
        AppOptions(include_settings=False, include_ops=True),
        bot_config=bot_config,
    )
    cmds = _handler_commands(app)
    assert "settings" not in cmds
    assert "pull" in cmds
