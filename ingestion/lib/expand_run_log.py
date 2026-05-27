"""Expand run jsonl logging and terminal output helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openrouter_client import OpenRouterCompletion
import paths


def expand_run_log_path() -> Path:
    return paths.ROOT / "catalog" / "expand-run.jsonl"


def expand_log_context_from_env() -> dict[str, str]:
    """Optional tune correlation (set by expand_tune subprocess env)."""
    out: dict[str, str] = {}
    run_id = os.environ.get("EXPAND_RUN_ID", "").strip()
    variant = os.environ.get("EXPAND_VARIANT", "").strip()
    if run_id:
        out["run_id"] = run_id
    if variant:
        out["variant"] = variant
    return out


def append_expand_run_log(record: dict[str, Any]) -> None:
    log_path = expand_run_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_expand_event(record: dict[str, Any]) -> dict[str, Any]:
    """Append one expand-run.jsonl row (merges tune env context)."""
    merged = {**expand_log_context_from_env(), **record}
    append_expand_run_log(merged)
    return merged


def load_expand_run_log() -> list[dict[str, Any]]:
    path = expand_run_log_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def filter_expand_run_log(
    records: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    variant: str | None = None,
    last: int | None = None,
) -> list[dict[str, Any]]:
    out = records
    if run_id:
        out = [r for r in out if r.get("run_id") == run_id]
    if variant:
        out = [r for r in out if r.get("variant") == variant]
    if last is not None and last > 0:
        out = out[-last:]
    return out


def format_duration_sec(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "?"
    return f"{duration_ms / 1000:.1f}s"


def format_cost_usd(cost: float | None) -> str:
    if cost is None:
        return "?"
    if cost >= 0.01:
        return f"${cost:.2f}"
    if cost > 0:
        return f"${cost:.4f}"
    return "$0"


def format_compact_chars(n: int) -> str:
    """Human-readable char count (e.g. 54k, 1.2M)."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.2f}M"


def format_compact_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def openrouter_completion_log_fields(
    completion: OpenRouterCompletion | None,
) -> dict[str, Any]:
    """Token/cost fields for expand-run.jsonl when a completion exists."""
    if completion is None:
        return {}
    return {
        "response_id": completion.response_id,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
        "total_tokens": completion.total_tokens,
        "cost_usd": completion.cost_usd,
        "duration_ms": completion.duration_ms,
    }


def format_expand_usage_suffix(completion: OpenRouterCompletion) -> str:
    return (
        f"{format_compact_tokens(completion.prompt_tokens)} in / "
        f"{format_compact_tokens(completion.completion_tokens)} out  "
        f"{format_cost_usd(completion.cost_usd)}  "
        f"{format_duration_sec(completion.duration_ms)}"
    )


def print_expand_ok_line(
    *,
    episode_id: str,
    completion: OpenRouterCompletion,
    draft_rel: str,
) -> None:
    print(
        f"[ok] {episode_id}  "
        f"{format_expand_usage_suffix(completion)}  "
        f"→ {draft_rel}"
    )


def print_expand_error_line(
    *,
    episode_id: str,
    error: str,
    completion: OpenRouterCompletion | None = None,
) -> None:
    print(f"[error] {episode_id}: {error}")
    if completion is not None:
        print(f"         {format_expand_usage_suffix(completion)}")


def print_expand_batch_summary(
    records: list[dict[str, Any]],
    *,
    title: str | None = None,
) -> None:
    if not records:
        return
    if title:
        print()
        print(title)
    counts: dict[str, int] = {}
    prompt_tok = 0
    completion_tok = 0
    cost_sum = 0.0
    cost_known = 0
    for r in records:
        status = r.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        if status == "ok":
            prompt_tok += int(r.get("prompt_tokens") or 0)
            completion_tok += int(r.get("completion_tokens") or 0)
            c = r.get("cost_usd")
            if c is not None:
                cost_sum += float(c)
                cost_known += 1
    print(
        f"  ok: {counts.get('ok', 0)}  "
        f"skipped: {counts.get('skipped', 0)}  "
        f"error: {counts.get('error', 0)}"
    )
    if prompt_tok or completion_tok:
        print(
            f"  tokens: {prompt_tok:,} in / {completion_tok:,} out"
        )
    if cost_known:
        print(f"  cost: ${cost_sum:.4f} ({cost_known} call(s) with usage.cost)")
    print(f"  log: {expand_run_log_path().relative_to(paths.ROOT)}")
