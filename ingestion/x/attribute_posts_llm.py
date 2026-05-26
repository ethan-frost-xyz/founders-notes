#!/usr/bin/env python3
"""Attribute ambiguous X posts in post-mapping-review.jsonl via OpenRouter."""

from __future__ import annotations
import sys
from pathlib import Path

_INGESTION = Path(__file__).resolve().parents[1]
if str(_INGESTION) not in sys.path:
    sys.path.insert(0, str(_INGESTION))

import _bootstrap

_bootstrap.setup_paths(__file__)

import argparse
import json
import os
import re
from typing import Any

from dotenv import load_dotenv

from catalog import catalog_by_number, load_catalog
from expand_llm import call_openrouter
from markdown_io import write_post_md
from paths import ROOT
from x_posts_csv import (
    POST_MAPPING_REVIEW,
    load_csv_rows,
    tweet_url,
)
from x_posts_match import AUTO_ACCEPT_SCORE, match_episode

load_dotenv(ROOT / ".env")

DEFAULT_ATTRIBUTION_MODEL = "openai/gpt-4o-mini"
MIN_CONFIDENCE = 0.7
MAX_CATALOG_LINES = 450


def load_review_records() -> list[dict[str, Any]]:
    if not POST_MAPPING_REVIEW.exists():
        return []
    records: list[dict[str, Any]] = []
    with POST_MAPPING_REVIEW.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_review_records(records: list[dict[str, Any]]) -> None:
    POST_MAPPING_REVIEW.parent.mkdir(parents=True, exist_ok=True)
    with POST_MAPPING_REVIEW.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def csv_by_post_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {r["x_post_id"]: r for r in rows if r.get("x_post_id")}


def build_catalog_context(rows: list[dict[str, Any]]) -> str:
    numbered = sorted(
        [r for r in rows if r.get("episode_number") is not None],
        key=lambda r: r["episode_number"],
    )
    lines: list[str] = []
    for r in numbered[:MAX_CATALOG_LINES]:
        num = r["episode_number"]
        title = (r.get("title") or "").strip()
        pub = (r.get("published_at") or "")[:10]
        lines.append(f"{num}\t{pub}\t{title}")
    return "\n".join(lines)


def parse_llm_attribution_response(raw: str) -> dict[str, Any]:
    """Parse model JSON; raises ValueError on invalid shape."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    ep = data.get("episode_number")
    if ep is not None and not isinstance(ep, int):
        if isinstance(ep, str) and ep.isdigit():
            data["episode_number"] = int(ep)
        else:
            raise ValueError("episode_number must be int or null")
    conf = data.get("confidence")
    if conf is not None:
        data["confidence"] = float(conf)
    return data


def attribution_prompt(text: str, catalog_context: str) -> str:
    return (
        "You map the user's X post to at most one Founders podcast episode.\n"
        "Return JSON only: "
        '{"episode_number": <int or null>, "confidence": <0-1>, "reason": "<short>"}\n'
        "Use null when not a Founders episode post or unclear.\n"
        "Prefer explicit episode numbers in the text (e.g. #131, ep. 131).\n\n"
        f"Catalog (episode_number, published_at, title):\n{catalog_context}\n\n"
        f"Post text:\n{text}"
    )


def call_attribution_llm(
    *,
    text: str,
    catalog_context: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    raw = call_openrouter(
        system="You attribute X posts to Founders podcast episodes. Respond with JSON only.",
        user=attribution_prompt(text, catalog_context),
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        response_format={"type": "json_object"},
    )
    return parse_llm_attribution_response(raw)


def resolve_attribution_model(cli_model: str | None) -> str:
    if cli_model:
        return cli_model
    env_model = os.environ.get("OPENROUTER_ATTRIBUTION_MODEL", "").strip()
    return env_model or DEFAULT_ATTRIBUTION_MODEL


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM attribution for post-mapping-review.jsonl rows"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print proposals only")
    parser.add_argument("--apply", action="store_true", help="Write .post.md for confident matches")
    parser.add_argument("--model", help="Override OPENROUTER_ATTRIBUTION_MODEL")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY in .env")
    model = resolve_attribution_model(args.model)
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or None

    review = load_review_records()
    if not review:
        print(f"No rows in {POST_MAPPING_REVIEW.relative_to(ROOT)}")
        return

    catalog_rows = load_catalog()
    by_number = catalog_by_number(catalog_rows)
    catalog_context = build_catalog_context(catalog_rows)
    csv_rows = load_csv_rows()
    by_id = csv_by_post_id(csv_rows)
    username = os.environ.get("X_USERNAME", "ethanfrost").strip().lstrip("@")

    remaining: list[dict[str, Any]] = []
    applied = 0

    for rec in review:
        post_id = rec["x_post_id"]
        csv_row = by_id.get(post_id)
        if csv_row and (csv_row.get("post_kind") or "").lower() == "article":
            print(f"[skip-article] {post_id}")
            remaining.append(rec)
            continue

        text = (rec.get("text_excerpt") or "").strip()
        if csv_row and (csv_row.get("text") or "").strip():
            text = csv_row["text"].strip()

        explicit_row, explicit_score, _ = match_episode(
            text, rec.get("published_at"), by_number
        )
        if explicit_row and explicit_score >= AUTO_ACCEPT_SCORE:
            ep_num = explicit_row["episode_number"]
            print(f"[explicit-skip] {post_id} → ep-{ep_num:04d} (use organize)")
            remaining.append(rec)
            continue

        try:
            result = call_attribution_llm(
                text=text,
                catalog_context=catalog_context,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
        except Exception as e:
            print(f"[error] {post_id}: {e}")
            remaining.append(rec)
            continue

        ep_num = result.get("episode_number")
        confidence = float(result.get("confidence") or 0)
        reason = result.get("reason") or ""

        if ep_num is None or confidence < MIN_CONFIDENCE:
            print(
                f"[keep-review] {post_id} → none conf={confidence:.2f} — {reason[:60]}"
            )
            remaining.append(rec)
            continue

        row = by_number.get(ep_num)
        if not row:
            print(f"[keep-review] {post_id} → unknown ep {ep_num}")
            remaining.append(rec)
            continue

        ep_id = row["id"]
        if args.dry_run:
            print(f"[propose] {post_id} → {ep_id} conf={confidence:.2f} — {reason[:80]}")
            remaining.append(rec)
            continue

        write_post_md(
            row,
            text,
            x_url=tweet_url(username, post_id),
            x_post_id=post_id,
            published_at=rec.get("published_at"),
            source="llm_attribution",
            post_kind=csv_row.get("post_kind") if csv_row else "tweet",
            attribution_note=f"llm:{model} conf={confidence:.2f} {reason[:120]}",
        )
        print(f"[applied] {post_id} → {ep_id} conf={confidence:.2f}")
        applied += 1

    if args.apply:
        save_review_records(remaining)
        print(f"Applied {applied}; {len(remaining)} rows remain in review queue")


if __name__ == "__main__":
    main()
