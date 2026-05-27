"""Subprocess orchestrator for vault index refresh (chunks + optional embeddings)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_TAIL_LINES = 40


def _python(vault_root: Path, override: str | None = None) -> str:
    if override:
        return override
    venv = vault_root / "ingestion" / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return sys.executable


def _tail(text: str, max_lines: int = _TAIL_LINES) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return "\n".join(lines[-max_lines:])


def reindex_vault(
    vault_root: Path,
    *,
    embeddings: bool = True,
    python: str | None = None,
) -> tuple[int, str]:
    """Run search/build_chunks.py; optionally search/build_embeddings.py under vault_root/ingestion."""
    vault_root = vault_root.resolve()
    py = _python(vault_root, python)
    env = os.environ.copy()
    env["VAULT_ROOT"] = str(vault_root)
    cwd = str(vault_root / "ingestion")

    chunks = subprocess.run(
        [py, "search/build_chunks.py"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if chunks.returncode != 0:
        return chunks.returncode, _tail((chunks.stdout or "") + (chunks.stderr or ""))

    if not embeddings:
        return 0, "Reindexed chunks."

    emb = subprocess.run(
        [py, "search/build_embeddings.py"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if emb.returncode != 0:
        return emb.returncode, _tail((emb.stdout or "") + (emb.stderr or ""))
    return 0, "Reindexed chunks and embeddings."


def main() -> int:
    import _bootstrap

    _bootstrap.setup_paths(__file__)
    code, msg = reindex_vault(_bootstrap.resolve_vault_root())
    if code != 0:
        print(msg, file=sys.stderr)
        return code
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
