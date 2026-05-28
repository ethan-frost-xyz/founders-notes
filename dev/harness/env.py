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


def live_harness_preflight(repo_root: Path | None = None) -> tuple[bool, str, dict[str, object]]:
    """OpenRouter env + local vault index checks before live Librarian scenarios."""
    root = (repo_root or REPO_ROOT).resolve()
    meta: dict[str, object] = {"vault_root": str(root)}

    ok, reason = live_harness_ready()
    if not ok:
        return False, reason, meta

    chunks_path = root / "catalog" / "chunks.jsonl"
    if not chunks_path.is_file():
        return (
            False,
            f"missing {chunks_path.relative_to(root)} — run services/telegram/deploy/sync-and-index.sh",
            meta,
        )
    try:
        with chunks_path.open(encoding="utf-8") as f:
            chunk_count = sum(1 for line in f if line.strip())
    except OSError as exc:
        return False, f"cannot read chunks index: {exc}", meta
    meta["chunk_count"] = chunk_count
    if chunk_count < 100:
        return False, f"chunks index too small ({chunk_count} lines); rebuild index on this clone", meta

    emb = root / "catalog" / "embeddings.npy"
    meta["embeddings_present"] = emb.is_file()
    if not emb.is_file():
        return (
            False,
            "catalog/embeddings.npy missing — run sync-and-index.sh (needs OPENROUTER_EMBED_MODEL)",
            meta,
        )

    return True, "", meta


def format_preflight_report(meta: dict[str, object]) -> str:
    lines = [f"vault_root={meta.get('vault_root')}"]
    if "chunk_count" in meta:
        lines.append(f"chunk_count={meta['chunk_count']}")
    if meta.get("embeddings_present"):
        lines.append("embeddings_present=yes")
    model = os.environ.get("TELEGRAM_CHAT_MODEL", "").strip()
    if model:
        lines.append(f"TELEGRAM_CHAT_MODEL={model}")
    return "\n".join(lines)
