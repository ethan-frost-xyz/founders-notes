"""Add ingestion/ and ingestion/lib/ to sys.path for CLI scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def _ingestion_root(script_file: str | Path) -> Path:
    script_dir = Path(script_file).resolve().parent
    if script_dir.name == "ingestion":
        return script_dir
    return script_dir.parent


def setup_paths(script_file: str | Path | None = None) -> Path:
    """Ensure ingestion/ and ingestion/lib/ are on sys.path. Returns ingestion root."""
    ingestion = (
        _ingestion_root(script_file) if script_file is not None else Path(__file__).resolve().parent
    )
    for entry in (ingestion, ingestion / "lib"):
        s = str(entry)
        if s not in sys.path:
            sys.path.insert(0, s)
    return ingestion
