"""Ops lock and Telegram-facing wrappers around vault_ops."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from vault_ops import run_git_pull, run_reindex, run_sync

_LOCK = threading.Lock()


def try_acquire_ops_lock(bot_data: dict[str, Any]) -> bool:
    if bot_data.get("ops_lock_held"):
        return False
    acquired = _LOCK.acquire(blocking=False)
    if acquired:
        bot_data["ops_lock_held"] = True
    return acquired


def release_ops_lock(bot_data: dict[str, Any]) -> None:
    if bot_data.pop("ops_lock_held", False):
        _LOCK.release()


def ops_lock_held(bot_data: dict[str, Any]) -> bool:
    return bool(bot_data.get("ops_lock_held")) or _LOCK.locked()


def run_reindex_op(vault_root: Path) -> tuple[int, str]:
    return run_reindex(vault_root)


__all__ = [
    "ops_lock_held",
    "release_ops_lock",
    "run_git_pull",
    "run_reindex_op",
    "run_sync",
    "try_acquire_ops_lock",
]
