"""VaultAgent: OpenRouter agentic retrieval loop."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable

from agent_streaming import accumulate_streamed_message
from agent_tools import (
    assistant_message_dict,
    build_trace_summary,
    execute_tool,
    openrouter_tools,
    tool_result_content,
    trace_evidence_from_result,
    trace_queries,
)
from config import AgentConfig, load_agent_config
from librarian_prompt import build_system_message
from reply_sanitize import sanitize_librarian_reply
from tool_status import tool_status_label
from telemetry import NO_OP_COLLECTOR, TelemetryCollector, TurnTimerCollector
from turn_timing import TurnTimer

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
    timing: dict[str, Any] | None = None


def _episode_evidence_summary(
    turn_evidence: list[dict[str, Any]],
) -> tuple[list[str], int]:
    ep_ids = sorted({str(e.get("episode_id", "")) for e in turn_evidence if e.get("episode_id")})
    return ep_ids, len(turn_evidence)


def search_budget_nudge(turn_evidence: list[dict[str, Any]]) -> str:
    base = SEARCH_BUDGET_NUDGE
    if not turn_evidence:
        return base
    ep_ids, chunk_count = _episode_evidence_summary(turn_evidence)
    if not ep_ids:
        return f"{base} Evidence gathered: {chunk_count} chunks. Answer now; say if thin."
    ep_preview = ", ".join(ep_ids[:8])
    if len(ep_ids) > 8:
        ep_preview += f" (+{len(ep_ids) - 8} more)"
    return (
        f"{base} Evidence gathered: {ep_preview} ({chunk_count} chunks). "
        "Answer now; say if thin."
    )


def cap_thin_evidence_reply(turn_evidence: list[dict[str, Any]]) -> str:
    """User-visible fallback when cap synthesis is empty after sanitization."""
    ep_ids, chunk_count = _episode_evidence_summary(turn_evidence)
    if ep_ids:
        ep_preview = ", ".join(ep_ids[:8])
        if len(ep_ids) > 8:
            ep_preview += f" (+{len(ep_ids) - 8} more)"
        gathered = (
            f"I searched episodes including {ep_preview} ({chunk_count} evidence chunks) "
            "but could not turn that into a clean answer."
        )
    elif turn_evidence:
        gathered = (
            f"I gathered {chunk_count} evidence chunks but could not turn that "
            "into a clean answer."
        )
    else:
        gathered = (
            "I used the full search budget for this turn but could not turn the "
            "results into a clean answer."
        )
    return (
        f"{gathered} The vault may not have a direct hit here — try a guest name, "
        "episode number, or a narrower theme."
    )


def finalize_librarian_content(
    raw: str,
    *,
    turn_evidence: list[dict[str, Any]],
    cap: bool,
) -> str:
    cleaned = sanitize_librarian_reply(raw)
    if cleaned:
        return cleaned
    if cap and turn_evidence:
        return cap_thin_evidence_reply(turn_evidence)
    return EMPTY_SYNTHESIS


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
        timing: TurnTimer | None = None,
        telemetry: TelemetryCollector | None = None,
    ) -> TurnResult:
        """Cold-start agentic loop: model drives retrieval via tools, then answers."""
        cfg = self.config
        trace: list[dict[str, Any]] = []
        stop_reason = "natural"
        collector = telemetry if telemetry is not None else NO_OP_COLLECTOR
        span_collector = collector if isinstance(collector, TurnTimerCollector) else None

        def _finish(
            *,
            content: str,
            steps: int,
            stop: str,
            error: bool = False,
        ) -> TurnResult:
            timing_dict = None
            if timing is not None:
                timing_dict = timing.to_dict()
                timing_dict["stop_reason"] = stop
                timing_dict["agent_steps"] = steps
                trace.append({"record": "timing", **timing_dict})
            if span_collector is not None:
                spans_record = span_collector.to_trace_record()
                if spans_record is not None:
                    trace.append(spans_record)
            summary = build_trace_summary(trace, stop_reason=stop)
            clean = finalize_librarian_content(
                content,
                turn_evidence=turn_evidence,
                cap=(stop == "cap"),
            )
            return TurnResult(
                content=clean,
                tool_trace=trace,
                trace_summary=summary,
                steps=steps,
                stop_reason=stop,
                error=error,
                timing=timing_dict,
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_system_message(cfg)},
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
        agent_round = 0

        def _completion(*, label: str, **kwargs: Any) -> SimpleNamespace:
            stream = kwargs.pop("stream", False)
            if stream:
                if "stream_options" not in kwargs:
                    kwargs["stream_options"] = {"include_usage": True}
                return accumulate_streamed_message(
                    completion_fn(**kwargs, stream=True),
                    on_chunk=on_chunk,
                    timing=timing,
                    label=label,
                )
            response = completion_fn(**kwargs)
            return response.choices[0].message

        def _timed_completion(
            *,
            label: str,
            phase_name: str,
            phase_attrs: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> SimpleNamespace:
            t0 = time.perf_counter()
            msg = _completion(label=label, **kwargs)
            ms = int((time.perf_counter() - t0) * 1000)
            attrs = dict(phase_attrs or {})
            attrs.setdefault("label", label)
            collector.record_phase(phase_name, ms, attrs=attrs)
            return msg

        try:
            tool_round = 0
            step = 0
            turn_evidence: list[dict[str, Any]] = []
            while True:
                step += 1
                agent_round += 1
                request: dict[str, Any] = {
                    "model": cfg.model,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    "tools": tools,
                    "tool_choice": "auto",
                }
                routing_label = f"agent_round_{agent_round}"
                t_route = time.perf_counter()
                msg = _completion(label=routing_label, **request)
                route_ms = int((time.perf_counter() - t_route) * 1000)

                if not msg.tool_calls:
                    collector.record_phase(
                        "agent.synthesis.final",
                        route_ms,
                        attrs={"round": agent_round, "stop": "natural", "label": routing_label},
                    )
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
                    return _finish(
                        content=msg.content or "",
                        steps=step,
                        stop=stop_reason,
                    )

                collector.record_phase(
                    "agent.routing",
                    route_ms,
                    attrs={"round": agent_round, "label": routing_label},
                )
                messages.append(assistant_message_dict(msg))
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
                    round_queries.extend(trace_queries(name, args))
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
                    result = execute_tool(
                        name,
                        args,
                        config=cfg,
                        history=history,
                        timing=timing,
                        telemetry=collector,
                    )
                    traced = trace_evidence_from_result(result)
                    round_evidence.extend(traced)
                    turn_evidence.extend(traced)
                    content = tool_result_content(result)
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
                        {"role": "system", "content": search_budget_nudge(turn_evidence)},
                    )
                    if on_tool_start is not None:
                        try:
                            on_tool_start("synthesis", {})
                        except Exception:
                            pass
                    agent_round += 1
                    cap_label = f"agent_round_{agent_round}_cap"
                    final = _timed_completion(
                        label=cap_label,
                        phase_name="agent.synthesis.final",
                        phase_attrs={"round": agent_round, "stop": "cap"},
                        model=cfg.model,
                        messages=messages,
                        stream=True,
                        stream_options={"include_usage": True},
                        tool_choice="none",
                    )
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
                    return _finish(
                        content=final.content or "",
                        steps=step + 1,
                        stop=stop_reason,
                    )
        except Exception as exc:
            return _finish(
                content=f"OpenRouter request failed: {exc}",
                steps=len(trace),
                stop="error",
                error=True,
            )
