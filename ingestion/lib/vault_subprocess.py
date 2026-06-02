"""Shared subprocess helpers for vault reindex and Janitor expand."""

from __future__ import annotations

import sys
from pathlib import Path

_DEFAULT_TAIL_LINES = 40


def python_executable(vault_root: Path, override: str | None = None) -> str:
    if override:
        return override
    venv = vault_root / "ingestion" / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return sys.executable


def tail_output(text: str, max_lines: int = _DEFAULT_TAIL_LINES) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return "\n".join(lines[-max_lines:])
