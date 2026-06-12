"""Librarian agent tool definitions and execution."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from config import AgentConfig
from evidence_format import format_load_episode_for_tool
from telemetry import TelemetryCollector
from turn_timing import TurnTimer

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


def openrouter_tools(*, default_k: int = 8) -> list[dict[str, Any]]:
    """Five-tool retrieval toolbox for the agentic Librarian loop."""
    _ = default_k
    return [
        {
            "type": "function",
            "function": {
                "name": "search_vault",
                "description": (
                    "Thematic / cross-episode retrieval over expanded notes and summaries. "
                    "Runs expand → hybrid search → rerank. Use for targeted vault search."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Focused search query.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_vault_many",
                "description": (
                    "Parallel decomposition: pass multiple sub-queries (e.g. one per founder "
                    "or thematic angle for multi-hop / cross-episode synthesis). "
                    "Each runs the full pipeline concurrently; results are labeled per sub-query. "
                    "Soft limit ~6 sub-queries."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of focused sub-queries.",
                        },
                    },
                    "required": ["queries"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_transcript",
                "description": (
                    "Keyword search over raw transcripts for verbatim dialogue or exact wording."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "k": {"type": "integer", "default": 8},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_episode",
                "description": (
                    "Load post, notes, and expanded for one episode (bounded size). "
                    "Use when the question is about a single founder in depth."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "episode_id": {
                            "type": "string",
                            "description": "Canonical ep-NNNN or bare episode number.",
                        },
                    },
                    "required": ["episode_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_episode_ids",
                "description": (
                    "Resolve a short token to ep-NNNN ids: episode number, guest name, or canonical id."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                    "required": ["query"],
                },
            },
        },
    ]


def _tool_handlers(
    config: AgentConfig,
    *,
    history: list[dict[str, Any]] | None = None,
    timing: TurnTimer | None = None,
    telemetry: TelemetryCollector | None = None,
    tool_round: int | None = None,
) -> dict[str, ToolFn]:
    from search_turn import (
        search_transcript_for_turn,
        search_vault_for_turn,
        search_vault_many_for_turn,
    )
    from vault import list_episode_ids, load_episode

    return {
        "search_vault": lambda args: search_vault_for_turn(
            str(args["query"]),
            config=config,
            history=history,
            timing=timing,
            telemetry=telemetry,
            tool_round=tool_round,
        ),
        "search_vault_many": lambda args: search_vault_many_for_turn(
            list(args.get("queries") or []),
            config=config,
            history=history,
            timing=timing,
            telemetry=telemetry,
            tool_round=tool_round,
        ),
        "search_transcript": lambda args: search_transcript_for_turn(
            str(args["query"]),
            config=config,
            k=int(args.get("k") or 8),
            timing=timing,
            telemetry=telemetry,
            tool_round=tool_round,
        ),
        "load_episode": lambda args: _timed_local_tool(
            timing,
            lambda: load_episode(str(args["episode_id"])),
        ),
        "list_episode_ids": lambda args: _timed_local_tool(
            timing,
            lambda: list_episode_ids(
                str(args["query"]),
                limit=int(args.get("limit") or 8),
            ),
        ),
    }


def _timed_local_tool(
    timing: TurnTimer | None,
    fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        return fn()
    finally:
        if timing is not None:
            timing.add_tool_local(int((time.perf_counter() - t0) * 1000))


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
    timing: TurnTimer | None = None,
    telemetry: TelemetryCollector | None = None,
    tool_round: int | None = None,
) -> dict[str, Any]:
    handlers = _tool_handlers(
        config,
        history=history,
        timing=timing,
        telemetry=telemetry,
        tool_round=tool_round,
    )
    if name not in handlers:
        return {"error": f"unknown tool: {name}"}
    try:
        return handlers[name](arguments)
    except Exception as exc:
        return {"error": str(exc)}


def assistant_message_dict(msg: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return out


def _is_load_episode_payload(payload: dict[str, Any]) -> bool:
    return (
        "episode_id" in payload
        and "sections" in payload
        and "evidence" not in payload
        and "error" not in payload
    )


def tool_result_content(payload: dict[str, Any]) -> str:
    """Serialize tool payload for the model; prefer readable evidence blocks."""
    if _is_load_episode_payload(payload):
        return format_load_episode_for_tool(payload)
    if "evidence" in payload and isinstance(payload["evidence"], str):
        meta = payload.get("meta")
        meta_line = ""
        if meta:
            meta_line = f"\n\n_meta: {json.dumps(meta, ensure_ascii=False)}"
        if "results" in payload:
            parts = [str(r.get("evidence") or r.get("error") or "") for r in payload["results"]]
            body = "\n\n---\n\n".join(p for p in parts if p)
            note = payload.get("note")
            if note:
                body = f"{note}\n\n{body}"
            return body + meta_line
        return str(payload["evidence"]) + meta_line
    return json.dumps(payload, ensure_ascii=False)


def trace_queries(tool_name: str, args: dict[str, Any]) -> list[str]:
    if tool_name == "search_vault_many":
        return [str(q) for q in (args.get("queries") or []) if str(q).strip()]
    if tool_name in {"search_vault", "search_transcript", "list_episode_ids"}:
        q = args.get("query")
        return [str(q)] if q else []
    if tool_name == "load_episode":
        ep = args.get("episode_id")
        return [str(ep)] if ep else []
    return []


def trace_evidence_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    if "trace_evidence" in result:
        return list(result.get("trace_evidence") or [])
    if "results" in result:
        merged: list[dict[str, Any]] = []
        for slot in result.get("results") or []:
            merged.extend(slot.get("trace_evidence") or [])
        return merged
    return []


def build_trace_summary(trace: list[dict[str, Any]], *, stop_reason: str) -> str:
    """Compact human-readable per-turn trace for tuning."""
    lines = [f"stop: {stop_reason}", ""]
    rounds = [t for t in trace if t.get("record") == "round"]
    if not rounds:
        return "\n".join(lines)
    for entry in rounds:
        r = entry.get("round", "?")
        tools = ", ".join(entry.get("tools") or [])
        queries = entry.get("queries") or []
        q_preview = "; ".join(queries[:3])
        if len(queries) > 3:
            q_preview += f" (+{len(queries) - 3} more)"
        ev = entry.get("evidence") or []
        ep_ids = sorted({e.get("episode_id", "") for e in ev if e.get("episode_id")})
        scores = [e.get("rerank_score") for e in ev if e.get("rerank_score") is not None]
        score_hint = f" top_scores={scores[:3]}" if scores else ""
        lines.append(f"round {r}: {tools or '(answer)'}")
        if q_preview:
            lines.append(f"  queries: {q_preview}")
        if ep_ids:
            lines.append(f"  episodes: {', '.join(ep_ids)}{score_hint}")
        reasoning = (entry.get("reasoning") or "").strip()
        if reasoning:
            lines.append(f"  reasoning: {reasoning[:200]}")
    return "\n".join(lines)
