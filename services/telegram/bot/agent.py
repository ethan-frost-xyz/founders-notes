"""OpenRouter vault agent: orchestrated retrieval + synthesis (Telegram Librarian)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tool_status import tool_status_label

from config import AgentConfig, load_agent_config

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "vault_agent.md"

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

# Explicit load/list turns must keep a tool round even when retrieval returned evidence.
_EXPLICIT_TOOL_TURN_RE = re.compile(
    r"(?i)"
    r"(\bload\s+episode\b"
    r"|\b(list|lookup)\s+episodes?\b"
    r"|\b(load|show|open)\b.{0,40}\bepisode\b)"
)


def user_wants_synthesis_tools(user_message: str) -> bool:
    return bool(_EXPLICIT_TOOL_TURN_RE.search(user_message.strip()))


@dataclass
class TurnResult:
    content: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    error: bool = False


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _build_system_message(config: AgentConfig, *, allow_web: bool) -> str:
    from index_status import index_metadata

    base = _load_system_prompt()
    meta = index_metadata(config.vault_root)
    meta_line = json.dumps(meta, separators=(",", ":"))
    web_flag = "true" if allow_web else "false"
    return (
        f"{base}\n\n---\n"
        f"Runtime: allow_web={web_flag}; index_metadata={meta_line}"
    )


def openrouter_tools(*, allow_web: bool, default_k: int = 8) -> list[dict[str, Any]]:
    """Optional tools for synthesis turn (load_episode escape hatch; web when allowed)."""
    _ = default_k
    tools: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "load_episode",
                "description": (
                    "Load post, notes, and expanded for one episode (bounded size). "
                    "Use when the user explicitly wants everything from one episode."
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
                    "Resolve a short token to ep-NNNN ids: episode number, guest name, or canonical id. "
                    "Use before load_episode when the user gives a bare number or guest name."
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
    if allow_web:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "External web search (only when allow_web=true).",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        )
    return tools


def _tool_handlers(config: AgentConfig) -> dict[str, ToolFn]:
    from web import web_search
    from vault import list_episode_ids, load_episode, search_transcript, search_vault_parent

    k_default = config.default_search_k

    return {
        "search_vault_parent": lambda args: search_vault_parent(
            str(args["query"]),
            int(args.get("k") or k_default),
        ),
        "search_transcript": lambda args: search_transcript(
            str(args["query"]),
            int(args.get("k") or k_default),
        ),
        "load_episode": lambda args: load_episode(str(args["episode_id"])),
        "list_episode_ids": lambda args: list_episode_ids(
            str(args["query"]),
            limit=int(args.get("limit") or 8),
        ),
        "web_search": lambda args: web_search(str(args.get("query", ""))),
    }


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    config: AgentConfig,
    allow_web: bool,
) -> dict[str, Any]:
    if name == "web_search" and not allow_web:
        return {"error": "web_search disabled for this turn"}
    handlers = _tool_handlers(config)
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


def _truncate_tool_json(payload: dict[str, Any], max_chars: int) -> str:
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    slim = dict(payload)
    slim["_truncated"] = True
    hits = slim.get("hits")
    if isinstance(hits, list) and len(hits) > 2:
        slim["hits"] = hits[:2]
    text = json.dumps(slim, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return json.dumps({"error": "tool result too large", "_truncated": True})


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
        allow_web: bool = False,
        session_id: str | None = None,
        completion_fn: Callable[..., Any] | None = None,
        on_tool_start: Callable[[str, dict[str, Any]], None] | None = None,
        retrieve_fn: Callable[..., Any] | None = None,
    ) -> TurnResult:
        """Retrieve evidence via orchestrator, then one synthesis completion (optional tools)."""
        cfg = self.config
        trace: list[dict[str, Any]] = []

        if retrieve_fn is None:
            from retrieval import retrieve_for_turn

            def retrieve_fn_inner(user_message: str, **kwargs: Any) -> Any:
                return retrieve_for_turn(user_message, **kwargs, config=cfg)

            retrieve_fn = retrieve_fn_inner

        status_seen: list[str] = []

        def on_status(label: str) -> None:
            status_seen.append(label)
            if on_tool_start is not None:
                try:
                    on_tool_start("retrieval", {"status": label})
                except Exception:
                    pass

        try:
            bundle = retrieve_fn(
                user_message,
                history=history,
                on_status=on_status,
            )
        except Exception as exc:
            return TurnResult(
                content=f"Retrieval failed: {exc}",
                tool_trace=trace,
                steps=0,
                error=True,
            )

        trace.append(
            {
                "step": 0,
                "tool": "retrieval_orchestrator",
                "arguments": {"query": user_message},
                "session_id": session_id,
                "retrieval_meta": bundle.retrieval_meta,
                "status_labels": status_seen,
            }
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _build_system_message(cfg, allow_web=allow_web)},
        ]
        if history:
            messages.extend(history)

        user_content = user_message
        if not bundle.skip_retrieval:
            from retrieval_orchestrator import format_evidence_for_synthesis

            evidence_block = format_evidence_for_synthesis(bundle)
            if evidence_block:
                user_content = f"{user_message}\n\n{evidence_block}"

        messages.append({"role": "user", "content": user_content})

        if completion_fn is None:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.api_key, base_url=cfg.openrouter_base_url)

            def completion_fn(**kwargs: Any) -> Any:
                return client.chat.completions.create(**kwargs)

        tools = openrouter_tools(allow_web=allow_web, default_k=cfg.default_search_k)
        tool_chars = 0
        has_evidence = not bundle.skip_retrieval and bool(bundle.chunks)
        wants_tools = user_wants_synthesis_tools(user_message)
        synthesis_only = bundle.skip_retrieval or (has_evidence and not wants_tools)
        max_steps = 1 if synthesis_only else 2

        try:
            for step in range(max_steps):
                is_final = step == max_steps - 1
                request: dict[str, Any] = {
                    "model": cfg.model,
                    "messages": messages,
                }
                if is_final or synthesis_only:
                    request["tool_choice"] = "none"
                else:
                    request["tools"] = tools
                    request["tool_choice"] = "auto"

                if on_tool_start is not None and is_final:
                    try:
                        on_tool_start("synthesis", {})
                    except Exception:
                        pass

                response = completion_fn(**request)
                msg = response.choices[0].message

                if is_final:
                    text = (msg.content or "").strip()
                    if not text:
                        text = (
                            "I could not compose an answer from the retrieved evidence. "
                            "Try a guest name, episode number, or a narrower theme."
                        )
                    return TurnResult(content=text, tool_trace=trace, steps=step + 1)

                if not msg.tool_calls:
                    text = (msg.content or "").strip()
                    if text:
                        return TurnResult(content=text, tool_trace=trace, steps=step + 1)
                    break

                messages.append(_assistant_message_dict(msg))
                remaining_budget = max(0, cfg.max_tool_result_chars - tool_chars)

                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    trace.append(
                        {
                            "step": step + 1,
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
                    per_tool_cap = max(500, remaining_budget // max(1, len(msg.tool_calls)))
                    result = execute_tool(
                        name,
                        args,
                        config=cfg,
                        allow_web=allow_web,
                    )
                    content = _truncate_tool_json(result, per_tool_cap)
                    tool_chars += len(content)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": content,
                        }
                    )

            return TurnResult(
                content="I could not finish an answer in one pass. Try rephrasing.",
                tool_trace=trace,
                steps=max_steps,
                error=True,
            )
        except Exception as exc:
            return TurnResult(
                content=f"OpenRouter request failed: {exc}",
                tool_trace=trace,
                steps=len(trace),
                error=True,
            )
