"""Vault path bootstrap: resolve repo root and add ingestion packages to sys.path.

CLI scripts call ``setup_paths(__file__)``. Telegram and tests use
``resolve_vault_root`` + ``setup_ingestion_paths`` (see docs/operations.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_INGESTION_DIR = Path(__file__).resolve().parent


def resolve_vault_root(explicit: Path | None = None) -> Path:
    """VAULT_ROOT env, else explicit, else parent of ingestion/ (from this module)."""
    if explicit is not None:
        return explicit.resolve()
    env = os.environ.get("VAULT_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return _INGESTION_DIR.parent


def setup_ingestion_paths(
    vault_root: Path | None = None,
    *,
    include_subpackages: bool = False,
) -> Path:
    """Idempotent sys.path for ingestion/, lib/, optional subpackages. Returns ingestion root."""
    root = resolve_vault_root(vault_root)
    os.environ.setdefault("VAULT_ROOT", str(root))
    ingestion = root / "ingestion"
    entries: list[Path] = [ingestion, ingestion / "lib"]
    if include_subpackages:
        for name in ("search", "notes", "x", "pipeline"):
            entries.append(ingestion / name)
    for entry in entries:
        s = str(entry)
        if s not in sys.path:
            sys.path.insert(0, s)
    return ingestion


def _ingestion_root(script_file: str | Path) -> Path:
    script_dir = Path(script_file).resolve().parent
    if script_dir.name == "ingestion":
        return script_dir
    return script_dir.parent


def setup_paths(script_file: str | Path | None = None) -> Path:
    """Ensure ingestion/ and ingestion/lib/ are on sys.path. Returns ingestion root."""
    if script_file is not None:
        ingestion = _ingestion_root(script_file)
        vault_root = ingestion.parent
    else:
        ingestion = _INGESTION_DIR
        vault_root = ingestion.parent
    return setup_ingestion_paths(vault_root)
