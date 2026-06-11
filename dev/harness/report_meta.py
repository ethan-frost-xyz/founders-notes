"""Shared harness report metadata helpers."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

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


def harness_git_branch(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def harness_git_dirty(repo_root: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return bool(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _runtime_json_path() -> Path:
    runtime_path = os.environ.get("FOUNDERS_TELEGRAM_RUNTIME", "").strip()
    if not runtime_path:
        runtime_path = str(Path.home() / ".config" / "founders-telegram" / "runtime.json")
    return Path(runtime_path)


def load_runtime_models() -> dict[str, str | None]:
    """Models from runtime.json with env overrides where set."""
    runtime_path = _runtime_json_path()
    data: dict[str, Any] = {}
    if runtime_path.is_file():
        try:
            parsed = json.loads(runtime_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, json.JSONDecodeError):
            pass

    librarian = os.environ.get("TELEGRAM_CHAT_MODEL", "").strip() or None
    if not librarian:
        lib = data.get("librarian_model")
        librarian = lib.strip() if isinstance(lib, str) and lib.strip() else None

    retrieval = os.environ.get("TELEGRAM_RETRIEVAL_MODEL", "").strip() or None
    if not retrieval:
        ret = data.get("retrieval_model")
        retrieval = ret.strip() if isinstance(ret, str) and ret.strip() else None

    embed = os.environ.get("OPENROUTER_EMBED_MODEL", "").strip() or None
    if not embed:
        emb = data.get("embed_model")
        embed = emb.strip() if isinstance(emb, str) and emb.strip() else None

    return {
        "runtime_path": str(runtime_path),
        "librarian_model": librarian,
        "retrieval_model": retrieval,
        "embed_model": embed,
    }


def build_run_context(
    repo_root: Path,
    scenario_paths: list[Path],
    *,
    run_note: str | None = None,
) -> dict[str, Any]:
    """Provenance block stamped on every harness report and suite-history row."""
    models = load_runtime_models()
    ctx: dict[str, Any] = {
        "git_sha": harness_git_sha(repo_root),
        "git_branch": harness_git_branch(repo_root),
        "git_dirty": harness_git_dirty(repo_root),
        "librarian_model": models.get("librarian_model"),
        "retrieval_model": models.get("retrieval_model"),
        "embed_model": models.get("embed_model"),
        "runtime_path": models.get("runtime_path"),
    }
    note = (run_note or os.environ.get("HARNESS_RUN_NOTE") or "").strip()
    if note:
        ctx["run_note"] = note
    if len(scenario_paths) == 1:
        path = scenario_paths[0]
        ctx["scenario_yaml"] = path.name
        try:
            ctx["scenario_path"] = str(path.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            ctx["scenario_path"] = str(path.resolve())
    elif scenario_paths:
        ctx["scenario_yamls"] = [p.name for p in scenario_paths]
    return ctx
