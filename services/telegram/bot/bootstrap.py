"""Single entry for Telegram bot Python path bootstrap."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_BOT_DIR = Path(__file__).resolve().parent
_TOOLS_DIR = _BOT_DIR / "tools"
_TELEGRAM_LIB = _BOT_DIR.parent / "lib"


def _resolve_root_hint(vault_root: Path | None) -> Path:
    if vault_root is not None:
        return vault_root.resolve()
    env = os.environ.get("VAULT_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return _BOT_DIR.parents[2]


def setup_telegram_paths(vault_root: Path | None = None) -> Path:
    """Add ingestion, bot, tools, and telegram lib to sys.path. Returns vault root."""
    ingestion = _resolve_root_hint(vault_root) / "ingestion"
    if str(ingestion) not in sys.path:
        sys.path.insert(0, str(ingestion))

    from _bootstrap import resolve_vault_root, setup_ingestion_paths

    root = resolve_vault_root(vault_root)
    setup_ingestion_paths(root)
    for entry in (str(_BOT_DIR), str(_TOOLS_DIR), str(_TELEGRAM_LIB)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return root
