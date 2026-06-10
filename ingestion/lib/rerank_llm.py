"""LLM reranker for retrieval orchestrator candidates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "rerank_evidence.md"


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in rerank response")
    return json.loads(text[start : end + 1])


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    base_url: str | None = None,
    max_excerpt_chars: int = 600,
) -> list[dict[str, Any]]:
    """Return candidates ordered by LLM relevance score (descending)."""
    if not candidates:
        return []

    lines: list[str] = []
    for i, ch in enumerate(candidates, start=1):
        excerpt = (ch.get("excerpt") or "")[:max_excerpt_chars]
        lines.append(
            f"{i}. chunk_id={ch.get('chunk_id')} | title={ch.get('title') or ''} | "
            f"section={ch.get('section') or ''}\n{excerpt}"
        )

    system = PROMPT_PATH.read_text(encoding="utf-8").strip()
    user = f"User query:\n{query}\n\nCandidates:\n" + "\n\n".join(lines)

    from openrouter_client import call_openrouter

    result = call_openrouter(
        system=system,
        user=user,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    payload = _extract_json_object(result.content)
    ranked = payload.get("ranked") or []
    score_by_id: dict[str, tuple[float, str]] = {}
    for row in ranked:
        if not isinstance(row, dict):
            continue
        cid = row.get("chunk_id")
        if not cid:
            continue
        try:
            score = float(row.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        score_by_id[str(cid)] = (score, str(row.get("rationale") or ""))

    by_id = {ch.get("chunk_id"): ch for ch in candidates if ch.get("chunk_id")}
    ordered_ids = sorted(
        score_by_id.keys(),
        key=lambda cid: (-score_by_id[cid][0], cid),
    )
    out: list[dict[str, Any]] = []
    for cid in ordered_ids:
        if cid not in by_id:
            continue
        ch = dict(by_id[cid])
        score, rationale = score_by_id[cid]
        ch["rerank_score"] = score
        ch["rerank_rationale"] = rationale
        out.append(ch)
    for ch in candidates:
        cid = ch.get("chunk_id")
        if cid and cid not in score_by_id:
            copy = dict(ch)
            copy["rerank_score"] = 0.0
            copy["rerank_rationale"] = ""
            out.append(copy)
    return out
