"""Shared mocks for Telegram handler unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("telegram")

from config import AgentConfig, BotConfig  # noqa: E402
from janitor_store import JanitorStore  # noqa: E402
from sessions import SessionStore  # noqa: E402


@dataclass
class MockMessage:
    """Minimal Message stand-in for handler tests."""

    text: str = ""
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reply_text: AsyncMock = field(default_factory=AsyncMock)
    reply_chat_action: AsyncMock = field(default_factory=AsyncMock)
    edit_text: AsyncMock = field(default_factory=AsyncMock)
    delete: AsyncMock = field(default_factory=AsyncMock)
    chat: MagicMock = field(default_factory=MagicMock)
    message_id: int = 1

    def __post_init__(self) -> None:
        self.chat.id = 1


@dataclass
class MockCallbackQuery:
    data: str
    message: MockMessage
    answer: AsyncMock = field(default_factory=AsyncMock)

    async def edit_message_text(self, text: str, **kwargs: Any) -> None:
        await self.message.edit_text(text, **kwargs)


@dataclass
class MockUser:
    id: int = 111


@dataclass
class MockUpdate:
    message: MockMessage | None = None
    callback_query: MockCallbackQuery | None = None
    effective_user: MockUser = field(default_factory=MockUser)


def make_bot_config(
    repo: Path,
    tmp_path: Path,
    *,
    user_ids: frozenset[int] = frozenset({111}),
    janitor_clean_model: str | None = "test/janitor-clean",
) -> BotConfig:
    sessions_dir = tmp_path / "telegram-sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    agent = AgentConfig(
        api_key="test-key",
        model="test/librarian",
        vault_root=repo,
    )
    return BotConfig(
        agent=agent,
        telegram_token="test-token",
        allowed_user_ids=user_ids,
        sessions_dir=sessions_dir,
        janitor_clean_model=janitor_clean_model,
    )


def make_context(
    bot_config: BotConfig,
    *,
    agent: Any | None = None,
    username: str | None = None,
) -> MagicMock:
    """Build a ContextTypes-like mock with bot_data populated."""
    sessions = SessionStore(bot_config)
    janitor = JanitorStore()
    bot_data: dict[str, Any] = {
        "config": bot_config,
        "agent": agent,
        "sessions": sessions,
        "janitor": janitor,
    }
    application = MagicMock()
    application.bot_data = bot_data
    application.bot = MagicMock()
    application.bot.username = username
    context = MagicMock()
    context.application = application
    context.user_data = {}
    return context


def text_update(text: str, *, user_id: int = 111) -> MockUpdate:
    return MockUpdate(
        message=MockMessage(text=text),
        effective_user=MockUser(id=user_id),
    )


def callback_update(data: str, *, user_id: int = 111) -> MockUpdate:
    msg = MockMessage()
    return MockUpdate(
        callback_query=MockCallbackQuery(data=data, message=msg),
        effective_user=MockUser(id=user_id),
    )
