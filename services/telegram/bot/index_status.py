"""Read-only vault index metadata for Telegram UI and agent system prompts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def index_metadata(vault_root: Path) -> dict[str, Any]:
    """Chunk count, embedding presence, and optional git SHA for agent runtime."""
    from paths import catalog_paths

    meta: dict[str, Any] = {}
    cp = catalog_paths(vault_root)
    if cp.chunks.is_file():
        try:
            with cp.chunks.open(encoding="utf-8") as f:
                meta["chunk_count"] = sum(1 for line in f if line.strip())
        except OSError:
            pass
    manifest = cp.embeddings_manifest
    emb = cp.embeddings
    if manifest.is_file():
        try:
            meta["embeddings_manifest_mtime"] = manifest.stat().st_mtime
        except OSError:
            pass
    meta["embeddings_present"] = emb.is_file()
    sha = _git_short_sha(vault_root)
    if sha:
        meta["git_sha"] = sha
    return meta


def vault_stats_text(vault_root: Path) -> str:
    """Human-readable index summary for /start and ops messages."""
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(vault_root)
    from catalog import load_catalog
    from gaps_report import count_phase2_coverage

    from paths import catalog_paths

    chunks_path = catalog_paths(vault_root).chunks
    rows = load_catalog()
    episodes = len(rows)
    _, studied, _, _, _, _, _ = count_phase2_coverage(rows)
    indexed = "unknown"
    if chunks_path.is_file():
        mtime = datetime.fromtimestamp(chunks_path.stat().st_mtime, tz=timezone.utc)
        indexed = mtime.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Episodes in catalog: {episodes}\n"
        f"Studied (timestamp bullets): {studied}\n"
        f"Chunks index updated: {indexed}"
    )


def _git_short_sha(vault_root: Path) -> str | None:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(vault_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None
