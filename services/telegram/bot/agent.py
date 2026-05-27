"""OpenRouter tool-calling loop for the Founders vault agent (SP2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from config import AgentConfig, load_agent_config

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "vault_agent.md"

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class TurnResult:
    content: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    error: bool = False


def _ensure_tool_paths(vault_root: Path) -> None:
    os.environ.setdefault("VAULT_ROOT", str(vault_root))
    tools_dir = Path(__file__).resolve().parent / "tools"
    bot_dir = Path(__file__).resolve().parent
    for entry in (str(tools_dir), str(bot_dir)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    ingestion = vault_root / "ingestion"
    lib = ingestion / "lib"
    for entry in (str(ingestion), str(lib)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _git_short_sha(vault_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(vault_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _index_metadata(vault_root: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    chunks_path = vault_root / "catalog" / "chunks.jsonl"
    if chunks_path.is_file():
        try:
            with chunks_path.open(encoding="utf-8") as f:
                meta["chunk_count"] = sum(1 for line in f if line.strip())
        except OSError:
            pass
    manifest = vault_root / "catalog" / "embeddings-manifest.jsonl"
    emb = vault_root / "catalog" / "embeddings.npy"
    if manifest.is_file():
        try:
            meta["embeddings_manifest_mtime"] = manifest.stat().st_mtime
        except OSError:
            pass
    meta["embeddings_present"] = emb.is_file()
    sha = _git_short_sha(vault_root)
    if sha:
        meta["git_sha"] = sha
    return meta


def _build_system_message(config: AgentConfig, *, allow_web: bool) -> str:
    base = _load_system_prompt()
    meta = _index_metadata(config.vault_root)
    meta_line = json.dumps(meta, separators=(",", ":"))
    web_flag = "true" if allow_web else "false"
    return (
        f"{base}\n\n---\n"
        f"Runtime: allow_web={web_flag}; index_metadata={meta_line}"
    )


def openrouter_tools(*, allow_web: bool, default_k: int = 8) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "search_vault_parent",
                "description": (
                    "Hybrid search over posts, raw notes, and promoted expanded notes. "
                    "Use for cross-episode themes and study material."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "k": {
                            "type": "integer",
                            "description": "Max hits (default 8)",
                            "default": default_k,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_transcript",
                "description": (
                    "Keyword search transcript chunks only. Use when dialogue wording matters."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "k": {"type": "integer", "default": default_k},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_episode",
                "description": "Load post, notes, and expanded files for one episode (bounded size).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "episode_id": {
                            "type": "string",
                            "description": "Canonical id e.g. ep-0022",
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
                "description": "Resolve episode number or fuzzy title to ep-NNNN ids.",
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


def web_search_stub(query: str) -> dict[str, Any]:
    """Backward-compatible alias for tests; delegates to tools.web."""
    from web import web_search

    return web_search(query)


def _tool_handlers(config: AgentConfig) -> dict[str, ToolFn]:
    from web import web_search
    from vault import (
        list_episode_ids,
        load_episode,
        search_transcript,
        search_vault_parent,
    )

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


class VaultAgent:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or load_agent_config()
        _ensure_tool_paths(self.config.vault_root)

    def run_turn(
        self,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
        allow_web: bool = False,
        session_id: str | None = None,
        completion_fn: Callable[..., Any] | None = None,
    ) -> TurnResult:
        """Run one user turn: tool loop until final assistant text or max_steps."""
        cfg = self.config
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _build_system_message(cfg, allow_web=allow_web)},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        tools = openrouter_tools(allow_web=allow_web, default_k=cfg.default_search_k)
        trace: list[dict[str, Any]] = []
        tool_chars = 0

        if completion_fn is None:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.api_key, base_url=cfg.openrouter_base_url)

            def completion_fn(**kwargs: Any) -> Any:
                return client.chat.completions.create(**kwargs)

        try:
            for step in range(cfg.max_steps):
                response = completion_fn(
                    model=cfg.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )
                msg = response.choices[0].message
                if not msg.tool_calls:
                    text = (msg.content or "").strip()
                    if not text:
                        text = "I could not produce an answer. Try rephrasing or narrowing the episode."
                    return TurnResult(content=text, tool_trace=trace, steps=step + 1)

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
                        }
                    )
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
                content="I hit the step limit while searching. Try a narrower question.",
                tool_trace=trace,
                steps=cfg.max_steps,
                error=True,
            )
        except Exception as exc:
            _ = session_id
            return TurnResult(
                content=f"OpenRouter request failed: {exc}",
                tool_trace=trace,
                steps=len(trace),
                error=True,
            )
