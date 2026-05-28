"""Environment loading for live mock Telegram harness runs."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_harness_env(repo_root: Path | None = None) -> list[Path]:
    """Load Telegram + repo dotenv files without overriding existing os.environ."""
    from dotenv import load_dotenv

    root = repo_root or REPO_ROOT
    loaded: list[Path] = []

    founders = os.environ.get("FOUNDERS_TELEGRAM_ENV", "").strip()
    if not founders:
        founders = str(Path.home() / ".config" / "founders-telegram" / "env")
    founders_path = Path(founders)
    if founders_path.is_file():
        load_dotenv(founders_path, override=False)
        loaded.append(founders_path)

    repo_env = root / ".env"
    if repo_env.is_file():
        load_dotenv(repo_env, override=False)
        loaded.append(repo_env)

    os.environ.setdefault("VAULT_ROOT", str(root.resolve()))
    return loaded


def live_harness_ready() -> tuple[bool, str]:
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        return False, "OPENROUTER_API_KEY not set (source ~/.config/founders-telegram/env or repo .env)"
    if not os.environ.get("TELEGRAM_CHAT_MODEL", "").strip():
        return False, "TELEGRAM_CHAT_MODEL not set"
    return True, ""
