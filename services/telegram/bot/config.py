"""Environment configuration for the vault Telegram agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _vault_root_default() -> Path:
    env = os.environ.get("VAULT_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class AgentConfig:
    api_key: str
    model: str
    vault_root: Path
    max_steps: int = 5
    max_tool_result_chars: int = 20_000
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_search_k: int = 8


@dataclass(frozen=True)
class BotConfig:
    agent: AgentConfig
    telegram_token: str
    allowed_user_ids: frozenset[int]
    sessions_dir: Path
    janitor_clean_model: str | None = None


def load_agent_config() -> AgentConfig:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("TELEGRAM_CHAT_MODEL", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required")
    if not model:
        raise ValueError(
            "TELEGRAM_CHAT_MODEL is required. Source ~/.config/founders-telegram/env "
            "(see services/telegram/deploy/env.example), not the repo root .env."
        )

    max_steps_raw = os.environ.get("TELEGRAM_MAX_STEPS", "").strip()
    max_steps = int(max_steps_raw) if max_steps_raw else 5
    if max_steps < 1:
        raise ValueError("TELEGRAM_MAX_STEPS must be >= 1")

    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"

    return AgentConfig(
        api_key=api_key,
        model=model,
        vault_root=_vault_root_default(),
        max_steps=max_steps,
        openrouter_base_url=base_url.rstrip("/"),
    )


def load_bot_config() -> BotConfig:
    agent = load_agent_config()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    ids_raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not ids_raw:
        raise ValueError("TELEGRAM_ALLOWED_USER_IDS is required")
    allowed: set[int] = set()
    for part in ids_raw.split(","):
        part = part.strip()
        if part:
            allowed.add(int(part))
    if not allowed:
        raise ValueError("TELEGRAM_ALLOWED_USER_IDS must list at least one user id")

    sessions_dir = agent.vault_root / "catalog" / "telegram-sessions"
    janitor_clean = os.environ.get("JANITOR_CLEAN_MODEL", "").strip() or None
    return BotConfig(
        agent=agent,
        telegram_token=token,
        allowed_user_ids=frozenset(allowed),
        sessions_dir=sessions_dir,
        janitor_clean_model=janitor_clean,
    )
