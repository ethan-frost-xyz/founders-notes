"""Environment configuration for the vault Telegram agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _vault_root_default() -> Path:
    from _bootstrap import resolve_vault_root

    return resolve_vault_root()


def setup_bot_paths(vault_root: Path | None = None) -> Path:
    """Bootstrap ingestion packages and telegram bot/tools on sys.path."""
    from bootstrap import setup_telegram_paths

    return setup_telegram_paths(vault_root)


@dataclass(frozen=True)
class AgentConfig:
    api_key: str
    model: str
    vault_root: Path
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
    from runtime_settings import apply_runtime_overrides, effective_librarian_model

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required")

    model, _ = effective_librarian_model()
    if not model:
        raise ValueError(
            "Librarian model is required. Set librarian_model in runtime.json "
            "(/setmodel librarian <slug>), TELEGRAM_CHAT_MODEL in env, or restart once to seed from env."
        )

    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"

    base = AgentConfig(
        api_key=api_key,
        model=model,
        vault_root=_vault_root_default(),
        openrouter_base_url=base_url.rstrip("/"),
    )
    return apply_runtime_overrides(base)


def load_bot_config() -> BotConfig:
    from runtime_settings import apply_runtime_to_bot_config, sync_embed_to_os_environ

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

    bot = BotConfig(
        agent=agent,
        telegram_token=token,
        allowed_user_ids=frozenset(allowed),
        sessions_dir=agent.vault_root / "catalog" / "telegram-sessions",
        janitor_clean_model=None,
    )
    bot = apply_runtime_to_bot_config(bot)
    sync_embed_to_os_environ()
    return bot
