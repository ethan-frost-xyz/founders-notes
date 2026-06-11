"""Shared harness report metadata helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPORT_SCHEMA_VERSION = "2.0"


def harness_git_sha(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
