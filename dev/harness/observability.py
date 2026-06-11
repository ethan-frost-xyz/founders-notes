"""Derive harness observability metrics from tool traces and responses."""

from __future__ import annotations

import re
from typing import Any

MAX_TOOL_ROUNDS = 6
_EPISODE_CITATION_RE = re.compile(r"\[ep-(\d{4})\]")
_DSML_LEAK_RE = re.compile(r"<\s*/?\s*dsml\b", re.IGNORECASE)

_RETRIEVAL_PHASE_PREFIX = "retrieval."


def spans_from_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for entry in reversed(traces):
        if entry.get("record") == "spans":
            return list(entry.get("spans") or [])
    return []


def _sum_span_ms(spans: list[dict[str, Any]], prefix: str) -> int:
    total = 0
    for span in spans:
        name = str(span.get("name") or "")
        if prefix.endswith("."):
            if name.startswith(prefix):
                total += int(span.get("ms") or 0)
        elif name == prefix:
            total += int(span.get("ms") or 0)
    return total


def _sum_span_exact(spans: list[dict[str, Any]], name: str) -> int:
    return _sum_span_ms(spans, name)


def agent_path_from_traces(
    traces: list[dict[str, Any]],
    *,
    tool_rounds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from harness.trace_report import tool_calls_from_traces, tool_rounds_from_traces

    calls = tool_calls_from_traces(traces)
    sequence = [str(c.get("tool") or "") for c in calls if c.get("tool")]
    rounds = tool_rounds if tool_rounds is not None else tool_rounds_from_traces(traces)
    tool_rounds_used = max((int(r.get("round") or 0) for r in rounds), default=0)
    reasoning_snippets = [
        str(r.get("reasoning") or "").strip()
        for r in rounds
        if str(r.get("reasoning") or "").strip()
    ]
    return {
        "sequence": sequence,
        "path_string": " -> ".join(sequence) if sequence else "",
        "tool_rounds_used": tool_rounds_used,
        "max_tool_rounds": MAX_TOOL_ROUNDS,
        "reasoning_snippets": reasoning_snippets,
    }


def routing_efficiency_from_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    from harness.trace_report import tool_calls_from_traces, tool_rounds_from_traces

    calls = tool_calls_from_traces(traces)
    sequence = [str(c.get("tool") or "") for c in calls if c.get("tool")]

    normalized_queries: list[str] = []
    for call in calls:
        args = call.get("arguments") or {}
        if "query" in args:
            normalized_queries.append(str(args["query"]).strip().lower())
        elif "queries" in args:
            for q in args.get("queries") or []:
                normalized_queries.append(str(q).strip().lower())

    seen: set[str] = set()
    redundant: list[str] = []
    for q in normalized_queries:
        if not q:
            continue
        if q in seen and q not in redundant:
            redundant.append(q)
        seen.add(q)

    tool_switches = 0
    for i in range(1, len(sequence)):
        if sequence[i] != sequence[i - 1]:
            tool_switches += 1

    search_before_load = False
    for rnd in tool_rounds_from_traces(traces):
        tools = list(rnd.get("tools") or [])
        if any(t in ("search_vault", "search_vault_many", "search_transcript") for t in tools):
            if "load_episode" in tools:
                search_before_load = True
                break

    return {
        "redundant_queries": redundant,
        "search_before_load_pattern": search_before_load,
        "tool_switches": tool_switches,
    }


def evidence_yield_from_traces(tool_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    chunks_per_round: list[int] = []
    unique_episodes_per_round: list[int] = []
    rerank_top_score_per_round: list[float | None] = []

    for rnd in tool_rounds:
        ev = list(rnd.get("evidence") or [])
        chunks_per_round.append(len(ev))
        ep_ids = {str(e.get("episode_id", "")) for e in ev if e.get("episode_id")}
        unique_episodes_per_round.append(len(ep_ids))
        scores = [float(e["rerank_score"]) for e in ev if e.get("rerank_score") is not None]
        rerank_top_score_per_round.append(max(scores) if scores else None)

    return {
        "chunks_per_round": chunks_per_round,
        "unique_episodes_per_round": unique_episodes_per_round,
        "rerank_top_score_per_round": rerank_top_score_per_round,
    }


def _chunk_key(ev: dict[str, Any]) -> str:
    cid = ev.get("chunk_id")
    if cid:
        return str(cid)
    ep = str(ev.get("episode_id") or "")
    section = str(ev.get("section") or "")
    return f"{ep}:{section}"


def cap_thrash_from_traces(
    tool_rounds: list[dict[str, Any]],
    *,
    stop_reason: str,
    response_text: str,
) -> dict[str, Any] | None:
    tool_rounds_used = max((int(r.get("round") or 0) for r in tool_rounds), default=0)
    hit_cap = stop_reason == "cap" or tool_rounds_used >= MAX_TOOL_ROUNDS
    if not hit_cap:
        return None

    round_chunks: dict[int, set[str]] = {}
    for rnd in tool_rounds:
        rnum = int(rnd.get("round") or 0)
        if rnum <= 0:
            continue
        keys = {_chunk_key(e) for e in (rnd.get("evidence") or [])}
        round_chunks[rnum] = keys

    all_chunks: set[str] = set()
    for keys in round_chunks.values():
        all_chunks |= keys

    total_unique = len(all_chunks)
    first_keys = round_chunks.get(1, set())
    final_round = max(round_chunks.keys()) if round_chunks else 0
    final_keys = round_chunks.get(final_round, set())

    first_share = len(first_keys) / total_unique if total_unique else 0.0
    final_share = len(final_keys) / total_unique if total_unique else 0.0

    episode_first_round: dict[str, int] = {}
    for rnd in sorted(tool_rounds, key=lambda r: int(r.get("round") or 0)):
        rnum = int(rnd.get("round") or 0)
        for ep in rnd.get("episode_ids") or []:
            ep_s = str(ep)
            if ep_s and ep_s not in episode_first_round:
                episode_first_round[ep_s] = rnum

    cited_eps = sorted({f"ep-{m}" for m in _EPISODE_CITATION_RE.findall(response_text or "")})
    cited_from_final = 0
    for ep in cited_eps:
        first_r = episode_first_round.get(ep)
        if first_r is not None and first_r == final_round:
            cited_from_final += 1
    cited_final_share = cited_from_final / len(cited_eps) if cited_eps else None

    return {
        "hit_cap": True,
        "gathered": {
            "total_unique_chunks": total_unique,
            "first_round_share": round(first_share, 4),
            "final_round_share": round(final_share, 4),
            "thrash_score": round(final_share - first_share, 4),
        },
        "cited": {
            "episodes_in_response": cited_eps,
            "first_retrieval_round_by_episode": episode_first_round,
            "cited_from_final_round_share": (
                round(cited_final_share, 4) if cited_final_share is not None else None
            ),
        },
    }


def _final_synthesis_call(timing: dict[str, Any] | None, stop_reason: str) -> dict[str, Any] | None:
    if not timing:
        return None
    calls = list(timing.get("openrouter_calls") or [])
    if not calls:
        return None
    cap_call = next((c for c in reversed(calls) if str(c.get("label") or "").endswith("_cap")), None)
    if cap_call:
        return cap_call
    if stop_reason == "natural":
        return calls[-1]
    return calls[-1]


def latency_from_traces(
    traces: list[dict[str, Any]],
    *,
    elapsed_s: float,
    timing: dict[str, Any] | None,
    stop_reason: str,
    accountability: dict[str, Any] | None,
) -> dict[str, Any]:
    spans = spans_from_traces(traces)
    wall_ms = int(round(elapsed_s * 1000))

    retrieval: dict[str, int] = {}
    for span in spans:
        name = str(span.get("name") or "")
        if name.startswith(_RETRIEVAL_PHASE_PREFIX):
            short = name[len(_RETRIEVAL_PHASE_PREFIX) :]
            retrieval[f"{short}_ms"] = retrieval.get(f"{short}_ms", 0) + int(span.get("ms") or 0)

    agent_routing_ms = _sum_span_exact(spans, "agent.routing")
    tool_local_ms = int((timing or {}).get("tool_local_ms") or 0)

    synthesis: dict[str, Any] = {}
    final_call = _final_synthesis_call(timing, stop_reason)
    if final_call:
        synthesis = {
            "final_ttft_ms": final_call.get("ttft_ms"),
            "final_total_ms": final_call.get("total_ms"),
            "label": final_call.get("label"),
        }

    return {
        "wall_ms": wall_ms,
        "agent_routing_ms": agent_routing_ms,
        "retrieval": retrieval,
        "tool_local_ms": tool_local_ms,
        "synthesis": synthesis,
        "accountability": accountability,
    }


def synthesis_quality_from_traces(
    response_text: str,
    *,
    timing: dict[str, Any] | None,
    stop_reason: str,
) -> dict[str, Any]:
    citations = _EPISODE_CITATION_RE.findall(response_text or "")
    final_call = _final_synthesis_call(timing, stop_reason)
    return {
        "citation_count": len(citations),
        "dsml_leak": bool(_DSML_LEAK_RE.search(response_text or "")),
        "final_synthesis_ttft_ms": final_call.get("ttft_ms") if final_call else None,
    }


def build_observability(
    traces: list[dict[str, Any]],
    *,
    response_text: str,
    elapsed_s: float,
    timing: dict[str, Any] | None,
    stop_reason: str,
    accountability: dict[str, Any] | None,
    tool_rounds: list[dict[str, Any]],
    timing_enabled: bool = True,
) -> dict[str, Any]:
    if not timing_enabled:
        return {"timing_enabled": False}

    agent_path = agent_path_from_traces(traces, tool_rounds=tool_rounds)
    cap_thrash = cap_thrash_from_traces(
        tool_rounds,
        stop_reason=stop_reason,
        response_text=response_text,
    )
    out: dict[str, Any] = {
        "timing_enabled": True,
        "agent_path": agent_path,
        "routing_efficiency": routing_efficiency_from_traces(traces),
        "latency": latency_from_traces(
            traces,
            elapsed_s=elapsed_s,
            timing=timing,
            stop_reason=stop_reason,
            accountability=accountability,
        ),
        "evidence_yield": evidence_yield_from_traces(tool_rounds),
        "synthesis_quality": synthesis_quality_from_traces(
            response_text,
            timing=timing,
            stop_reason=stop_reason,
        ),
    }
    if cap_thrash is not None:
        out["cap_thrash"] = cap_thrash
    return out


def aggregate_observability(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate observability across turns that recorded metrics."""
    obs_turns = [t.get("observability") for t in turns if t.get("observability", {}).get("timing_enabled")]
    if not obs_turns:
        return {}

    cap_hits = sum(1 for o in obs_turns if (o.get("cap_thrash") or {}).get("hit_cap"))
    final_ttfts = [
        o.get("latency", {}).get("synthesis", {}).get("final_ttft_ms")
        for o in obs_turns
        if o.get("latency", {}).get("synthesis", {}).get("final_ttft_ms") is not None
    ]
    thrash_scores = [
        o["cap_thrash"]["gathered"]["thrash_score"]
        for o in obs_turns
        if o.get("cap_thrash") and o["cap_thrash"].get("gathered")
    ]
    walls = [o.get("latency", {}).get("wall_ms") for o in obs_turns if o.get("latency")]

    agg: dict[str, Any] = {
        "turn_count": len(obs_turns),
        "cap_hits": cap_hits,
    }
    if final_ttfts:
        agg["mean_final_ttft_ms"] = round(sum(final_ttfts) / len(final_ttfts), 1)
    if thrash_scores:
        agg["mean_thrash_score"] = round(sum(thrash_scores) / len(thrash_scores), 4)
    if walls:
        agg["mean_wall_ms"] = round(sum(walls) / len(walls), 1)
    return agg
