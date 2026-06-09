"""Extract structured report fields from harness tool traces and replies."""

from __future__ import annotations

from typing import Any, Protocol


class _ReplyLike(Protocol):
    text: str


def response_text_from_replies(replies: list[_ReplyLike]) -> str:
    parts = [r.text.strip() for r in replies if r.text and r.text.strip()]
    return "\n\n".join(parts)


def tool_calls_from_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in traces:
        tool = entry.get("tool")
        if not tool:
            continue
        out.append(
            {
                "step": entry.get("step"),
                "tool": str(tool),
                "arguments": dict(entry.get("arguments") or {}),
            }
        )
    return out


def tool_call_counts_from_traces(traces: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in traces:
        tool = entry.get("tool")
        if not tool:
            continue
        name = str(tool)
        counts[name] = counts.get(name, 0) + 1
    return counts


def tool_rounds_from_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    for entry in traces:
        if entry.get("record") != "round":
            continue
        ev = entry.get("evidence") or []
        ep_ids = sorted({str(e.get("episode_id", "")) for e in ev if e.get("episode_id")})
        scores = [float(e["rerank_score"]) for e in ev if e.get("rerank_score") is not None]
        reasoning = (entry.get("reasoning") or "").strip()
        row: dict[str, Any] = {
            "round": entry.get("round"),
            "tools": list(entry.get("tools") or []),
            "queries": list(entry.get("queries") or []),
            "episode_ids": ep_ids,
            "rerank_scores_top3": scores[:3],
        }
        if entry.get("stop"):
            row["stop"] = entry["stop"]
        if reasoning:
            row["reasoning"] = reasoning
        rounds.append(row)
    return rounds


def stop_reason_from_traces(traces: list[dict[str, Any]], *, llm_mode: str = "live") -> str:
    timing = timing_dict_from_traces(traces)
    if timing:
        reason = timing.get("stop_reason")
        if reason:
            return str(reason)

    if timing:
        for call in timing.get("openrouter_calls") or []:
            label = str(call.get("label") or "")
            if label.endswith("_cap"):
                return "cap"

    for entry in traces:
        if entry.get("record") == "round" and entry.get("stop") == "cap":
            return "cap"

    tool_names = [t.get("tool") for t in traces if t.get("tool")]
    if llm_mode == "live" and tool_names and timing is None:
        return "error"

    return "natural"


def timing_dict_from_traces(traces: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in reversed(traces):
        if entry.get("record") == "timing":
            return {k: v for k, v in entry.items() if k != "record"}
    return None


def trace_summary_from_traces(traces: list[dict[str, Any]], stop_reason: str) -> str:
    try:
        from agent import build_trace_summary
    except ImportError:
        return ""
    return build_trace_summary(traces, stop_reason=stop_reason)


def timing_accountability(timing: dict[str, Any] | None, elapsed_s: float) -> dict[str, Any] | None:
    if not timing:
        return None

    vault_ms = int(timing.get("vault_search_local_ms") or 0)
    retrieval_ms = int(timing.get("retrieval_llm_ms") or 0)
    openrouter_total_ms = sum(
        int(c.get("total_ms") or 0) for c in (timing.get("openrouter_calls") or [])
    )
    accounted_ms = vault_ms + retrieval_ms + openrouter_total_ms
    wall_ms = int(round(elapsed_s * 1000))
    unaccounted_ms = max(0, wall_ms - accounted_ms)

    return {
        "wall_ms": wall_ms,
        "accounted_ms": accounted_ms,
        "unaccounted_ms": unaccounted_ms,
        "accounted_breakdown": {
            "vault_search_local_ms": vault_ms,
            "retrieval_llm_ms": retrieval_ms,
            "openrouter_total_ms": openrouter_total_ms,
        },
    }


def enrich_turn_from_traces(
    traces: list[dict[str, Any]],
    replies: list[_ReplyLike],
    *,
    elapsed_s: float,
    llm_mode: str = "live",
    assistant_content: str | None = None,
) -> dict[str, Any]:
    timing = timing_dict_from_traces(traces)
    stop_reason = stop_reason_from_traces(traces, llm_mode=llm_mode)
    if assistant_content is not None:
        response_text = assistant_content
    else:
        response_text = response_text_from_replies(replies)
    out: dict[str, Any] = {
        "response_text": response_text,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls_from_traces(traces),
        "tool_rounds": tool_rounds_from_traces(traces),
        "tool_call_counts": tool_call_counts_from_traces(traces),
        "trace_summary": trace_summary_from_traces(traces, stop_reason),
    }
    if timing is not None:
        out["timing"] = timing
        try:
            from turn_timing import summary_line_from_dict

            out["timing_summary"] = summary_line_from_dict(timing)
        except ImportError:
            out["timing_summary"] = None
        accountability = timing_accountability(timing, elapsed_s)
        if accountability is not None:
            out["timing_accountability"] = accountability
    return out
