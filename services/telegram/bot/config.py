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


def load_agent_config() -> AgentConfig:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("TELEGRAM_CHAT_MODEL", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required")
    if not model:
        raise ValueError("TELEGRAM_CHAT_MODEL is required")

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
