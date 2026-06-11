"""Shared vault git pull and reindex operations."""

from __future__ import annotations

import subprocess
from pathlib import Path

from runtime_settings import build_subprocess_env


def _clear_vault_read_caches(vault_root: Path) -> None:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(vault_root)
    from catalog import clear_jsonl_cache

    clear_jsonl_cache()


def run_git_pull(vault_root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=str(vault_root),
        capture_output=True,
        text=True,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        _clear_vault_read_caches(vault_root)
    return proc.returncode, log.strip() or "(no output)"


def run_reindex(vault_root: Path) -> tuple[int, str]:
    from _bootstrap import setup_ingestion_paths

    env = build_subprocess_env(vault_root=vault_root)
    setup_ingestion_paths(vault_root)
    from reindex_vault import reindex_vault

    code, msg = reindex_vault(vault_root, env=env)
    _clear_vault_read_caches(vault_root)
    return code, msg


def run_sync(vault_root: Path) -> tuple[int, str]:
    pull_code, pull_log = run_git_pull(vault_root)
    if pull_code != 0:
        return pull_code, f"Pull failed (exit {pull_code}).\n\n{pull_log}"
    idx_code, idx_log = run_reindex(vault_root)
    if idx_code != 0:
        return idx_code, f"Pull OK.\nReindex failed (exit {idx_code}).\n\n{idx_log}"
    return 0, f"Pull:\n{pull_log}\n\nReindex:\n{idx_log}"
