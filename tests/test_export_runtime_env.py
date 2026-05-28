"""Tests for runtime.json → shell export helper (sync-and-index.sh)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EXPORT_SCRIPT = REPO / "ingestion" / "lib" / "export_runtime_env.py"


def test_export_runtime_env_prints_embed_from_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime = tmp_path / "runtime.json"
    runtime.write_text(
        json.dumps({"embed_model": "qwen/qwen3-embedding-8b", "expand_model": "anthropic/claude-sonnet-4"}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_EMBED_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("FOUNDERS_TELEGRAM_RUNTIME", str(runtime))

    from lib.export_runtime_env import resolve_model_exports

    exports = resolve_model_exports()
    assert exports["OPENROUTER_EMBED_MODEL"] == "qwen/qwen3-embedding-8b"
    assert exports["OPENROUTER_MODEL"] == "anthropic/claude-sonnet-4"


def test_export_runtime_env_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime = tmp_path / "runtime.json"
    runtime.write_text(json.dumps({"embed_model": "custom/embed-model"}), encoding="utf-8")
    env = {**os.environ, "FOUNDERS_TELEGRAM_RUNTIME": str(runtime)}
    proc = subprocess.run(
        [str(REPO / "ingestion" / ".venv" / "bin" / "python"), str(EXPORT_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO / "ingestion"),
    )
    if proc.returncode != 0 and "No such file" in (proc.stderr or ""):
        proc = subprocess.run(
            ["python3", str(EXPORT_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO / "ingestion"),
        )
    assert proc.returncode == 0
    assert "OPENROUTER_EMBED_MODEL=custom/embed-model" in proc.stdout


def test_sync_script_sources_export_helper():
    text = (REPO / "services" / "telegram" / "deploy" / "sync-and-index.sh").read_text(
        encoding="utf-8"
    )
    assert "export_runtime_env.py" in text
    assert ".sync-in-progress" in text
