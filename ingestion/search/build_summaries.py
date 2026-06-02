#!/usr/bin/env python3
"""Build catalog/episode-summaries.jsonl (incremental LLM summaries for studied episodes)."""

from __future__ import annotations

import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import hashlib
import json
import os
from typing import Any

from dotenv import load_dotenv

from build_chunks import episode_is_studied
from catalog import load_catalog, load_jsonl
from markdown_io import read_markdown_body, utc_now_iso
import paths
from paths import expanded_file_path, notes_file_path, post_file_path

load_dotenv(paths.ROOT / ".env")

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "episode_summary.md"


def content_hash(expanded_text: str, post_text: str) -> str:
    payload = f"{expanded_text}\n---\n{post_text}"
    return hashlib.sha256(payload.encode()).hexdigest()


def load_existing_summaries(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return {
        row["episode_id"]: row
        for row in load_jsonl(path)
        if row.get("episode_id")
    }


def _read_optional(path: Path) -> str:
    if not path.is_file():
        return ""
    return read_markdown_body(path)


def generate_summary(
    *,
    title: str,
    expanded_text: str,
    post_text: str,
    model: str,
    api_key: str,
    base_url: str | None,
) -> str:
    from openrouter_client import call_openrouter

    system = PROMPT_PATH.read_text(encoding="utf-8").strip()
    user = (
        f"Episode title: {title}\n\n"
        f"## Expanded datapoints\n{expanded_text[:120_000]}\n\n"
        f"## Post\n{post_text[:20_000]}"
    )
    result = call_openrouter(
        system=system,
        user=user,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
    )
    return result.content.strip()


def build_episode_summaries(
    *,
    apply: bool = True,
    limit: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    rows = load_catalog()
    existing = load_existing_summaries(paths.EPISODE_SUMMARIES_PATH)
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = (model or os.environ.get("TELEGRAM_CHAT_MODEL") or os.environ.get("OPENROUTER_MODEL") or "").strip()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or None

    studied: list[tuple[dict[str, Any], str, str, str]] = []
    for row in rows:
        ep_id = row["id"]
        slug = row["slug"]
        num = row.get("episode_number")
        npath = notes_file_path(ep_id, slug, num)
        if not episode_is_studied(npath):
            continue
        expanded_path = expanded_file_path(ep_id, slug, num)
        if not expanded_path.is_file():
            continue
        expanded_text = _read_optional(expanded_path)
        post_text = _read_optional(post_file_path(ep_id, slug, num))
        if not expanded_text.strip():
            continue
        studied.append((row, expanded_text, post_text, content_hash(expanded_text, post_text)))

    studied.sort(key=lambda item: item[0].get("episode_number") or 0)
    if limit is not None:
        studied = studied[:limit]

    out_by_id: dict[str, dict[str, Any]] = {}
    to_generate: list[tuple[dict[str, Any], str, str, str]] = []

    for row, expanded_text, post_text, chash in studied:
        ep_id = row["id"]
        prev = existing.get(ep_id)
        if prev and prev.get("content_hash") == chash and prev.get("summary_text"):
            out_by_id[ep_id] = prev
            continue
        to_generate.append((row, expanded_text, post_text, chash))

    generated = 0
    if apply and to_generate:
        if not api_key or not model:
            raise SystemExit(
                "Set OPENROUTER_API_KEY and librarian model (runtime.json or TELEGRAM_CHAT_MODEL) for --apply"
            )
        for row, expanded_text, post_text, chash in to_generate:
            ep_id = row["id"]
            title = row.get("title") or ep_id
            summary_text = generate_summary(
                title=str(title),
                expanded_text=expanded_text,
                post_text=post_text,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            out_by_id[ep_id] = {
                "episode_id": ep_id,
                "title": title,
                "summary_text": summary_text,
                "content_hash": chash,
                "model": model,
                "generated_at": utc_now_iso(),
            }
            generated += 1

    final_rows = sorted(out_by_id.values(), key=lambda r: r.get("episode_id", ""))

    if apply:
        paths.EPISODE_SUMMARIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with paths.EPISODE_SUMMARIES_PATH.open("w", encoding="utf-8") as f:
            for row in final_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        from catalog import clear_jsonl_cache

        clear_jsonl_cache()

    return {
        "studied_with_expanded": len(studied),
        "reused": len(studied) - len(to_generate),
        "to_generate": len(to_generate),
        "generated": generated if apply else 0,
        "written": len(final_rows) if apply else len(studied),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build episode summary index rows")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    summary = build_episode_summaries(apply=not args.dry_run, limit=args.limit)
    print(
        f"studied={summary['studied_with_expanded']} reuse={summary['reused']} "
        f"generate={summary['to_generate']} written={summary.get('written', 0)}"
    )


if __name__ == "__main__":
    main()
