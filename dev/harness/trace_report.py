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
            "evidence": list(ev),
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


def _search_row_wall_ms(row: dict[str, Any]) -> int:
    wall = row.get("wall_ms")
    if wall is not None:
        return int(wall)
    vault = int(row.get("vault_search_local_ms") or 0)
    retrieval = int(row.get("retrieval_llm_ms") or 0)
    return vault + retrieval


def _search_accountable_ms(
    searches: list[dict[str, Any]],
    *,
    vault_ms: int,
    retrieval_ms: int,
    tool_batches: list[dict[str, Any]] | None = None,
) -> int:
    if not searches:
        return vault_ms + retrieval_ms

    parallel_rounds = {
        int(batch["tool_round"]): int(batch["wall_ms"])
        for batch in (tool_batches or [])
        if batch.get("parallel") and batch.get("tool_round") is not None
    }

    total = 0
    i = 0
    while i < len(searches):
        row = searches[i]
        tool_round = row.get("tool_round")
        if tool_round is not None and tool_round in parallel_rounds:
            while i < len(searches) and searches[i].get("tool_round") == tool_round:
                i += 1
            total += parallel_rounds[tool_round]
            continue
        if row.get("tool") == "search_vault_many":
            batch_walls: list[int] = []
            while i < len(searches) and searches[i].get("tool") == "search_vault_many":
                batch_walls.append(_search_row_wall_ms(searches[i]))
                i += 1
            total += max(batch_walls) if batch_walls else 0
        else:
            total += _search_row_wall_ms(row)
            i += 1
    return total


def timing_accountability(timing: dict[str, Any] | None, elapsed_s: float) -> dict[str, Any] | None:
    if not timing:
        return None

    vault_ms = int(timing.get("vault_search_local_ms") or 0)
    retrieval_ms = int(timing.get("retrieval_llm_ms") or 0)
    thread_wait_ms = int(timing.get("thread_wait_ms") or 0)
    expand_retry_ms = int(timing.get("expand_retry_ms") or 0)
    tool_local_ms = int(timing.get("tool_local_ms") or 0)
    searches = list(timing.get("searches") or [])
    tool_batches = list(timing.get("tool_batches") or [])
    openrouter_total_ms = sum(
        int(c.get("total_ms") or 0) for c in (timing.get("openrouter_calls") or [])
    )
    search_wall_ms = _search_accountable_ms(
        searches,
        vault_ms=vault_ms,
        retrieval_ms=retrieval_ms,
        tool_batches=tool_batches,
    )
    accounted_ms = search_wall_ms + tool_local_ms + openrouter_total_ms
    wall_ms = int(round(elapsed_s * 1000))
    unaccounted_ms = max(0, wall_ms - accounted_ms)
    parallelism_excess_ms = max(0, vault_ms + retrieval_ms - search_wall_ms)

    return {
        "wall_ms": wall_ms,
        "accounted_ms": accounted_ms,
        "unaccounted_ms": unaccounted_ms,
        "accounted_breakdown": {
            "search_wall_ms": search_wall_ms,
            "tool_local_ms": tool_local_ms,
            "openrouter_total_ms": openrouter_total_ms,
            "thread_wait_ms": thread_wait_ms,
            "expand_retry_ms": expand_retry_ms,
            "parallelism_excess_ms": parallelism_excess_ms,
            "vault_search_local_ms": vault_ms,
            "retrieval_llm_ms": retrieval_ms,
        },
    }


def enrich_turn_from_traces(
    traces: list[dict[str, Any]],
    replies: list[_ReplyLike],
    *,
    elapsed_s: float,
    llm_mode: str = "live",
    assistant_content: str | None = None,
    timing_enabled: bool = True,
) -> dict[str, Any]:
    timing = timing_dict_from_traces(traces)
    stop_reason = stop_reason_from_traces(traces, llm_mode=llm_mode)
    if assistant_content is not None:
        response_text = assistant_content
    else:
        response_text = response_text_from_replies(replies)
    tool_rounds = tool_rounds_from_traces(traces)
    out: dict[str, Any] = {
        "response_text": response_text,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls_from_traces(traces),
        "tool_rounds": tool_rounds,
        "tool_call_counts": tool_call_counts_from_traces(traces),
        "trace_summary": trace_summary_from_traces(traces, stop_reason),
    }
    accountability = None
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

    from harness.observability import build_observability

    out["observability"] = build_observability(
        traces,
        response_text=response_text,
        elapsed_s=elapsed_s,
        timing=timing,
        stop_reason=stop_reason,
        accountability=accountability,
        tool_rounds=tool_rounds,
        timing_enabled=timing_enabled and timing is not None,
    )
    return out
