"""OpenRouter vault agent: agentic retrieval loop + synthesis (Telegram Librarian)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from tool_status import tool_status_label

from config import AgentConfig, load_agent_config

_LEGACY_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "vault_agent.md"
)

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

MAX_TOOL_ROUNDS = 6
SEARCH_BUDGET_NUDGE = (
    "Search budget reached for this turn. Answer from the evidence gathered so far "
    "and be explicit if it is thin or incomplete."
)
EMPTY_SYNTHESIS = (
    "I could not compose an answer from the retrieved evidence. "
    "Try a guest name, episode number, or a narrower theme."
)


@dataclass
class TurnResult:
    content: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    trace_summary: str = ""
    steps: int = 0
    stop_reason: str = "natural"
    error: bool = False


def _load_system_prompt(vault_root: Path) -> str:
    path = vault_root / "AGENTS.md"
    if not path.is_file():
        path = _LEGACY_PROMPT_PATH
    return path.read_text(encoding="utf-8").strip()


def _build_system_message(config: AgentConfig) -> str:
    from index_status import index_metadata

    base = _load_system_prompt(config.vault_root)
    meta = index_metadata(config.vault_root)
    meta_line = json.dumps(meta, separators=(",", ":"))
    return f"{base}\n\n---\nRuntime: index_metadata={meta_line}"


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
                    "Parallel decomposition: pass multiple sub-queries (e.g. one per founder). "
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
) -> dict[str, ToolFn]:
    from retrieval import (
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
        ),
        "search_vault_many": lambda args: search_vault_many_for_turn(
            list(args.get("queries") or []),
            config=config,
            history=history,
        ),
        "search_transcript": lambda args: search_transcript_for_turn(
            str(args["query"]),
            config=config,
            k=int(args.get("k") or 8),
        ),
        "load_episode": lambda args: load_episode(str(args["episode_id"])),
        "list_episode_ids": lambda args: list_episode_ids(
            str(args["query"]),
            limit=int(args.get("limit") or 8),
        ),
    }


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    handlers = _tool_handlers(config, history=history)
    if name not in handlers:
        return {"error": f"unknown tool: {name}"}
    try:
        return handlers[name](arguments)
    except Exception as exc:
        return {"error": str(exc)}


def _assistant_message_dict(msg: Any) -> dict[str, Any]:
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


def _tool_result_content(payload: dict[str, Any]) -> str:
    """Serialize tool payload for the model; prefer readable evidence blocks."""
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


def _trace_queries(tool_name: str, args: dict[str, Any]) -> list[str]:
    if tool_name == "search_vault_many":
        return [str(q) for q in (args.get("queries") or []) if str(q).strip()]
    if tool_name in {"search_vault", "search_transcript", "list_episode_ids"}:
        q = args.get("query")
        return [str(q)] if q else []
    if tool_name == "load_episode":
        ep = args.get("episode_id")
        return [str(ep)] if ep else []
    return []


def _trace_evidence_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
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


def _accumulate_streamed_message(
    stream: Any,
    *,
    on_chunk: Callable[[str], None] | None,
) -> SimpleNamespace:
    content_parts: list[str] = []
    tool_calls_acc: dict[int, dict[str, Any]] = {}

    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            content_parts.append(delta.content)
            if on_chunk is not None:
                on_chunk(delta.content)
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                slot = tool_calls_acc.setdefault(
                    idx,
                    {"id": "", "name": "", "arguments_parts": []},
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function.arguments:
                        slot["arguments_parts"].append(tc.function.arguments)

    tool_calls = None
    if tool_calls_acc:
        tool_calls = []
        for idx in sorted(tool_calls_acc):
            slot = tool_calls_acc[idx]
            tool_calls.append(
                SimpleNamespace(
                    id=slot["id"] or f"call_{idx}",
                    function=SimpleNamespace(
                        name=slot["name"],
                        arguments="".join(slot["arguments_parts"]),
                    ),
                )
            )

    return SimpleNamespace(
        content="".join(content_parts) if content_parts else None,
        tool_calls=tool_calls,
    )


class VaultAgent:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or load_agent_config()
        from config import setup_bot_paths

        setup_bot_paths(self.config.vault_root)

    def run_turn(
        self,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
        session_id: str | None = None,
        completion_fn: Callable[..., Any] | None = None,
        on_tool_start: Callable[[str, dict[str, Any]], None] | None = None,
        on_chunk: Callable[[str], None] | None = None,
        retrieve_fn: Callable[..., Any] | None = None,
    ) -> TurnResult:
        """Cold-start agentic loop: model drives retrieval via tools, then answers."""
        _ = retrieve_fn  # legacy param; agentic loop does not pre-retrieve
        cfg = self.config
        trace: list[dict[str, Any]] = []
        stop_reason = "natural"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _build_system_message(cfg)},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        if completion_fn is None:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.api_key, base_url=cfg.openrouter_base_url)

            def completion_fn(**kwargs: Any) -> Any:
                return client.chat.completions.create(**kwargs)

        tools = openrouter_tools(default_k=cfg.default_search_k)

        def _completion(**kwargs: Any) -> SimpleNamespace:
            stream = kwargs.pop("stream", False)
            if stream:
                return _accumulate_streamed_message(
                    completion_fn(**kwargs, stream=True),
                    on_chunk=on_chunk,
                )
            response = completion_fn(**kwargs)
            return response.choices[0].message

        try:
            tool_round = 0
            step = 0
            while True:
                step += 1
                request: dict[str, Any] = {
                    "model": cfg.model,
                    "messages": messages,
                    "stream": True,
                    "tools": tools,
                    "tool_choice": "auto",
                }
                msg = _completion(**request)

                if not msg.tool_calls:
                    text = (msg.content or "").strip() or EMPTY_SYNTHESIS
                    trace.append(
                        {
                            "record": "round",
                            "round": tool_round + 1,
                            "tools": [],
                            "queries": [],
                            "evidence": [],
                            "reasoning": (msg.content or "").strip(),
                            "stop": "natural",
                            "session_id": session_id,
                        }
                    )
                    summary = build_trace_summary(trace, stop_reason=stop_reason)
                    return TurnResult(
                        content=text,
                        tool_trace=trace,
                        trace_summary=summary,
                        steps=step,
                        stop_reason=stop_reason,
                    )

                messages.append(_assistant_message_dict(msg))
                round_tools: list[str] = []
                round_queries: list[str] = []
                round_evidence: list[dict[str, Any]] = []

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    round_tools.append(name)
                    round_queries.extend(_trace_queries(name, args))
                    trace.append(
                        {
                            "step": tool_round + 1,
                            "tool": name,
                            "arguments": args,
                            "session_id": session_id,
                            "status_label": tool_status_label(name),
                        }
                    )
                    if on_tool_start is not None:
                        try:
                            on_tool_start(name, args)
                        except Exception:
                            pass
                    result = execute_tool(name, args, config=cfg, history=history)
                    round_evidence.extend(_trace_evidence_from_result(result))
                    content = _tool_result_content(result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": content,
                        }
                    )

                tool_round += 1
                trace.append(
                    {
                        "record": "round",
                        "round": tool_round,
                        "tools": round_tools,
                        "queries": round_queries,
                        "evidence": round_evidence,
                        "reasoning": (msg.content or "").strip(),
                        "session_id": session_id,
                    }
                )

                if tool_round >= MAX_TOOL_ROUNDS:
                    stop_reason = "cap"
                    messages.append(
                        {"role": "system", "content": SEARCH_BUDGET_NUDGE},
                    )
                    if on_tool_start is not None:
                        try:
                            on_tool_start("synthesis", {})
                        except Exception:
                            pass
                    final = _completion(
                        model=cfg.model,
                        messages=messages,
                        stream=True,
                        tool_choice="none",
                    )
                    text = (final.content or "").strip() or EMPTY_SYNTHESIS
                    trace.append(
                        {
                            "record": "round",
                            "round": tool_round + 1,
                            "tools": [],
                            "queries": [],
                            "evidence": [],
                            "reasoning": (final.content or "").strip(),
                            "stop": "cap",
                            "session_id": session_id,
                        }
                    )
                    summary = build_trace_summary(trace, stop_reason=stop_reason)
                    return TurnResult(
                        content=text,
                        tool_trace=trace,
                        trace_summary=summary,
                        steps=step + 1,
                        stop_reason=stop_reason,
                    )
        except Exception as exc:
            summary = build_trace_summary(trace, stop_reason="error")
            return TurnResult(
                content=f"OpenRouter request failed: {exc}",
                tool_trace=trace,
                trace_summary=summary,
                steps=len(trace),
                stop_reason="error",
                error=True,
            )
