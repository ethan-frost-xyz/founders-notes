"""File notes, expand/promote subprocesses, and reindex for Janitor mode."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_TAIL_LINES = 40
_DRAFT_EXCERPT_CHARS = 2800
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "janitor_clean.md"


def _ingestion_paths(vault_root: Path) -> None:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(vault_root)


def _python(vault_root: Path) -> str:
    venv = vault_root / "ingestion" / ".venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return sys.executable


def _tail(text: str, max_lines: int = _TAIL_LINES) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return "\n".join(lines[-max_lines:])


def load_janitor_clean_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def janitor_clean_temperature() -> float:
    from runtime_settings import effective_janitor_clean_temperature

    temp, _ = effective_janitor_clean_temperature()
    return temp


def build_clean_user_message(
    raw: str,
    *,
    episode_id: str | None = None,
    episode_title: str | None = None,
    current_draft: str | None = None,
    feedback: str | None = None,
) -> str:
    header = "Episode: (not set yet)"
    if episode_id:
        title_part = episode_title.strip() if episode_title else ""
        header = f"Episode: {episode_id}"
        if title_part:
            header += f" — {title_part}"
    parts = [header, "---", "Original paste:", raw.strip()]
    if current_draft and current_draft.strip():
        parts.extend(["---", "Current cleaned draft:", current_draft.strip()])
    if feedback and feedback.strip():
        parts.extend(["---", "User revision request:", feedback.strip()])
    return "\n".join(parts)


def resolve_catalog_row(vault_root: Path, episode_id: str) -> dict[str, Any]:
    _ingestion_paths(vault_root)
    from catalog import load_catalog, resolve_catalog_row as _resolve

    return _resolve(load_catalog(), episode_id)


def file_notes(vault_root: Path, row: dict[str, Any], cleaned_body: str) -> Path:
    _ingestion_paths(vault_root)
    from janitor_notes import merge_notes_body
    from markdown_io import read_markdown_body, write_notes_md
    import paths as vault_paths

    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    npath = vault_paths.notes_file_path(ep_id, slug, num)
    if npath.is_file():
        existing = read_markdown_body(npath)
        body = merge_notes_body(existing, cleaned_body)
    else:
        body = cleaned_body
    return write_notes_md(row, body, source="telegram_janitor")


def llm_clean_pasted_notes(
    raw: str,
    *,
    api_key: str,
    model: str,
    vault_root: Path,
    base_url: str | None = None,
    episode_id: str | None = None,
    episode_title: str | None = None,
    temperature: float | None = None,
    current_draft: str | None = None,
    feedback: str | None = None,
) -> tuple[str, list[str]]:
    """LLM-only paste normalization (no regex re-parse)."""
    _ingestion_paths(vault_root)
    from openrouter_client import call_openrouter
    from janitor_notes import finalize_notes_body

    if temperature is None:
        temperature = janitor_clean_temperature()

    completion = call_openrouter(
        system=load_janitor_clean_prompt(),
        user=build_clean_user_message(
            raw,
            episode_id=episode_id,
            episode_title=episode_title,
            current_draft=current_draft,
            feedback=feedback,
        ),
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        episode_id=episode_id,
    )
    return finalize_notes_body(completion.content)


def run_expand(vault_root: Path, episode_id: str, *, force: bool) -> tuple[int, str]:
    script = vault_root / "ingestion" / "notes" / "expand_datapoints_llm.py"
    cmd = [
        _python(vault_root),
        str(script),
        "--id",
        episode_id,
        "--apply",
        "--no-stream",
    ]
    if force:
        cmd.append("--force")
    from runtime_settings import build_subprocess_env

    env = build_subprocess_env(vault_root=vault_root)
    proc = subprocess.run(
        cmd,
        cwd=str(vault_root / "ingestion"),
        env=env,
        capture_output=True,
        text=True,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, _tail(log)


def run_promote(vault_root: Path, episode_id: str) -> tuple[int, str, list[str]]:
    _ingestion_paths(vault_root)
    from catalog import load_catalog, resolve_catalog_row as _resolve
    from expand_llm import promote_draft

    row = _resolve(load_catalog(), episode_id)
    path, errors, warnings = promote_draft(row, dry_run=False)
    if errors:
        return 1, "\n".join(errors), warnings
    rel = path.relative_to(vault_root) if path else Path("?")
    return 0, f"Promoted to {rel}", warnings


def run_reindex(vault_root: Path) -> tuple[int, str]:
    _ingestion_paths(vault_root)
    from reindex_vault import reindex_vault
    from runtime_settings import build_subprocess_env

    env = build_subprocess_env(vault_root=vault_root)
    return reindex_vault(vault_root, env=env)


def draft_excerpt(vault_root: Path, row: dict[str, Any]) -> str:
    _ingestion_paths(vault_root)
    from markdown_io import read_markdown_body
    import paths as vault_paths

    ep_id = row["id"]
    slug = row["slug"]
    num = row.get("episode_number")
    dpath = vault_paths.expanded_draft_file_path(ep_id, slug, num)
    if not dpath.is_file():
        return "(no draft file yet)"
    body = read_markdown_body(dpath)
    if len(body) <= _DRAFT_EXCERPT_CHARS:
        return body
    return body[:_DRAFT_EXCERPT_CHARS] + "\n…"
