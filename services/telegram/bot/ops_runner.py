"""Git pull and vault reindex ops for Telegram /pull, /reindex, /sync."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Any

from runtime_settings import build_subprocess_env

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


def run_git_pull(vault_root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=str(vault_root),
        capture_output=True,
        text=True,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, log.strip() or "(no output)"


def run_reindex_op(vault_root: Path) -> tuple[int, str]:
    from _bootstrap import setup_ingestion_paths

    env = build_subprocess_env(vault_root=vault_root)
    setup_ingestion_paths(vault_root)
    from reindex_vault import reindex_vault

    return reindex_vault(vault_root, env=env)


def run_sync(vault_root: Path) -> tuple[int, str]:
    pull_code, pull_log = run_git_pull(vault_root)
    if pull_code != 0:
        return pull_code, f"Pull failed (exit {pull_code}).\n\n{pull_log}"
    idx_code, idx_log = run_reindex_op(vault_root)
    if idx_code != 0:
        return idx_code, f"Pull OK.\nReindex failed (exit {idx_code}).\n\n{idx_log}"
    return 0, f"Pull:\n{pull_log}\n\nReindex:\n{idx_log}"
