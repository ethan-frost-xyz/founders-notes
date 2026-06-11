"""Subprocess orchestrator for vault index refresh (chunks + optional embeddings)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from vault_subprocess import python_executable, tail_output


def reindex_vault(
    vault_root: Path,
    *,
    embeddings: bool = True,
    python: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run search/build_chunks.py; optionally search/build_embeddings.py under vault_root/ingestion."""
    vault_root = vault_root.resolve()
    py = python_executable(vault_root, python)
    if env is None:
        env = os.environ.copy()
        env["VAULT_ROOT"] = str(vault_root)
    else:
        env = dict(env)
        env.setdefault("VAULT_ROOT", str(vault_root))
    cwd = str(vault_root / "ingestion")

    chunks = subprocess.run(
        [py, "search/build_chunks.py"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if chunks.returncode != 0:
        return chunks.returncode, tail_output((chunks.stdout or "") + (chunks.stderr or ""))

    summaries = subprocess.run(
        [py, "search/build_summaries.py"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if summaries.returncode != 0:
        return summaries.returncode, tail_output((summaries.stdout or "") + (summaries.stderr or ""))

    chunks2 = subprocess.run(
        [py, "search/build_chunks.py"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if chunks2.returncode != 0:
        return chunks2.returncode, tail_output((chunks2.stdout or "") + (chunks2.stderr or ""))

    if not embeddings:
        return 0, "Reindexed chunks and episode summaries."

    emb = subprocess.run(
        [py, "search/build_embeddings.py"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if emb.returncode != 0:
        return emb.returncode, tail_output((emb.stdout or "") + (emb.stderr or ""))
    return 0, "Reindexed chunks and embeddings."


def main() -> int:
    ingestion = Path(__file__).resolve().parents[1]
    ing = str(ingestion)
    if ing not in sys.path:
        sys.path.insert(0, ing)

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
