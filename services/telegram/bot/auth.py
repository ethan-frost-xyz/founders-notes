"""Telegram user allowlist."""

from __future__ import annotations

from config import BotConfig


def is_allowed(user_id: int | None, config: BotConfig) -> bool:
    if user_id is None:
        return False
    return int(user_id) in config.allowed_user_ids
