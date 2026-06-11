"""Telegram turn adapter for Librarian search tools (orchestrator-backed)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from config import AgentConfig
from evidence_format import format_evidence_for_tool
from retrieval.orchestrator import (
    EXPAND_VARIANTS_FULL,
    EXPAND_VARIANTS_LIGHT,
    SEARCH_VAULT_KEEP,
    SEARCH_VAULT_MANY_KEEP,
    SEARCH_VAULT_MANY_MAX,
    EvidenceBundle,
    RetrievalOrchestrator,
    evidence_meta_for_trace,
    orchestrator_from_agent_config,
)
from telemetry import TelemetryCollector
from turn_timing import TurnTimer


def _orchestrator(config: AgentConfig) -> RetrievalOrchestrator:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(config.vault_root)
    from runtime_settings import effective_retrieval_model

    retrieval_model, _ = effective_retrieval_model()
    return orchestrator_from_agent_config(config, retrieval_model=retrieval_model)


class _SearchTiming:
    """Per-search accumulator bridged to TurnTimer."""

    def __init__(self, timer: TurnTimer, query: str, *, tool: str) -> None:
        self._timer = timer
        self._query = query
        self._tool = tool
        self._t0 = time.perf_counter()
        self.vault_local_ms = 0
        self.retrieval_llm_ms = 0

    def on_timing(self, phase: str, ms: int) -> None:
        if phase == "vault_local":
            self.vault_local_ms += ms
            self._timer.add_vault_local(ms)
        elif phase == "retrieval_llm":
            self.retrieval_llm_ms += ms
            self._timer.add_retrieval_llm(ms)

    def finish(self, *, error: bool = False) -> None:
        wall_ms = int((time.perf_counter() - self._t0) * 1000)
        self._timer.record_search(
            self._query,
            vault_search_local_ms=self.vault_local_ms,
            retrieval_llm_ms=self.retrieval_llm_ms,
            wall_ms=wall_ms,
            tool=self._tool,
            error=error,
        )


def _timing_callback(timer: TurnTimer | None, search: _SearchTiming | None) -> Callable[[str, int], None] | None:
    if timer is None or search is None:
        return None

    def on_timing(phase: str, ms: int) -> None:
        search.on_timing(phase, ms)

    return on_timing


def _retry_callback(timer: TurnTimer | None) -> Callable[[int, int, int], None] | None:
    if timer is None:
        return None

    def on_retry(_failed_attempt: int, sleep_ms: int, failed_call_ms: int) -> None:
        timer.add_expand_retry(sleep_ms + failed_call_ms)

    return on_retry


def _phase_callback(
    telemetry: TelemetryCollector | None,
) -> Callable[[str, int], None] | None:
    if telemetry is None:
        return None

    def on_phase(name: str, ms: int) -> None:
        telemetry.record_phase(name, ms)

    return on_phase


def search_vault_for_turn(
    query: str,
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
    on_status: Callable[[str], None] | None = None,
    timing: TurnTimer | None = None,
    telemetry: TelemetryCollector | None = None,
) -> dict[str, Any]:
    """Full expand + hybrid + rerank; returns formatted evidence for the agent loop."""
    search_timing = (
        _SearchTiming(timing, query, tool="search_vault") if timing is not None else None
    )
    orch = _orchestrator(config)
    failed = False
    try:
        bundle = orch.retrieve_core(
            query,
            history=history,
            expand_variants=EXPAND_VARIANTS_FULL,
            keep=SEARCH_VAULT_KEEP,
            on_status=on_status,
            on_timing=_timing_callback(timing, search_timing),
            on_phase=_phase_callback(telemetry),
            on_retry=_retry_callback(timing),
        )
    except Exception:
        failed = True
        raise
    finally:
        if search_timing is not None:
            search_timing.finish(error=failed)
    return {
        "query": query,
        "evidence": format_evidence_for_tool(bundle, max_chunks=SEARCH_VAULT_KEEP),
        "meta": bundle.retrieval_meta,
        "trace_evidence": evidence_meta_for_trace(bundle),
    }


def search_vault_many_for_turn(
    queries: list[str],
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
    on_status: Callable[[str], None] | None = None,
    timing: TurnTimer | None = None,
    telemetry: TelemetryCollector | None = None,
) -> dict[str, Any]:
    """Concurrent fan-out of retrieve_core per sub-query; labeled results."""
    cleaned = [str(q).strip() for q in queries if str(q).strip()]
    truncated = False
    if len(cleaned) > SEARCH_VAULT_MANY_MAX:
        cleaned = cleaned[:SEARCH_VAULT_MANY_MAX]
        truncated = True

    if not cleaned:
        return {
            "error": "queries must contain at least one non-empty string",
            "results": [],
        }

    orch = _orchestrator(config)
    results: list[dict[str, Any]] = [None] * len(cleaned)  # type: ignore[list-item]

    def _run_one(idx: int, sub_query: str) -> tuple[int, dict[str, Any]]:
        search_timing = (
            _SearchTiming(timing, sub_query, tool="search_vault_many")
            if timing is not None
            else None
        )
        try:
            bundle = orch.retrieve_core(
                sub_query,
                history=history,
                expand_variants=EXPAND_VARIANTS_LIGHT,
                keep=SEARCH_VAULT_MANY_KEEP,
                on_status=on_status,
                on_timing=_timing_callback(timing, search_timing),
                on_phase=_phase_callback(telemetry),
                on_retry=_retry_callback(timing),
            )
            if search_timing is not None:
                search_timing.finish()
            return idx, {
                "query": sub_query,
                "evidence": format_evidence_for_tool(
                    bundle,
                    label=sub_query,
                    max_chunks=SEARCH_VAULT_MANY_KEEP,
                ),
                "meta": bundle.retrieval_meta,
                "trace_evidence": evidence_meta_for_trace(bundle),
            }
        except Exception as exc:
            if search_timing is not None:
                search_timing.finish(error=True)
            return idx, {
                "query": sub_query,
                "error": str(exc),
                "evidence": f"### {sub_query}\n\nSearch failed: {exc}",
                "trace_evidence": [],
            }

    t_batch = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(cleaned)) as ex:
        futures = [ex.submit(_run_one, i, q) for i, q in enumerate(cleaned)]
        for fut in as_completed(futures):
            idx, payload = fut.result()
            results[idx] = payload
    if timing is not None:
        timing.add_thread_wait(int((time.perf_counter() - t_batch) * 1000))

    out: dict[str, Any] = {"results": results}
    if truncated:
        out["truncated"] = True
        out["note"] = f"Processed first {SEARCH_VAULT_MANY_MAX} sub-queries only."
    return out


def search_transcript_for_turn(
    query: str,
    *,
    config: AgentConfig,
    k: int = 8,
    timing: TurnTimer | None = None,
    telemetry: TelemetryCollector | None = None,
) -> dict[str, Any]:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(config.vault_root)
    from search_retrieval import search_transcript_evidence

    from _bootstrap import resolve_vault_root

    from paths import catalog_paths

    root = resolve_vault_root(config.vault_root)
    chunks_path = catalog_paths(root).chunks
    t0 = time.perf_counter()
    result = search_transcript_evidence(query, k, chunks_path=chunks_path, root=root)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if timing is not None:
        timing.add_vault_local(elapsed_ms)
        timing.record_search(
            query,
            vault_search_local_ms=elapsed_ms,
            retrieval_llm_ms=0,
            wall_ms=elapsed_ms,
            tool="search_transcript",
        )
    if telemetry is not None:
        telemetry.record_phase("retrieval.transcript_search", elapsed_ms)
    from evidence_format import format_transcript_evidence, trace_evidence_from_hits

    hits = result.get("hits") or []
    evidence = format_transcript_evidence(hits)
    trace_evidence = trace_evidence_from_hits(hits)
    return {
        "query": query,
        "evidence": evidence,
        "meta": result.get("meta") or {},
        "trace_evidence": trace_evidence,
    }
