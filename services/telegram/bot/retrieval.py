"""Telegram adapter for ingestion retrieval orchestrator."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from config import AgentConfig
from retrieval_orchestrator import (
    EXPAND_VARIANTS_FULL,
    EXPAND_VARIANTS_NONE,
    SEARCH_VAULT_KEEP,
    SEARCH_VAULT_MANY_KEEP,
    SEARCH_VAULT_MANY_MAX,
    EvidenceBundle,
    RetrievalOrchestrator,
    evidence_meta_for_trace,
    format_evidence_for_tool,
    orchestrator_from_agent_config,
)


def _orchestrator(config: AgentConfig) -> RetrievalOrchestrator:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(config.vault_root)
    from runtime_settings import effective_retrieval_model

    retrieval_model, _ = effective_retrieval_model()
    return orchestrator_from_agent_config(config, retrieval_model=retrieval_model)


def search_vault_for_turn(
    query: str,
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Full expand + hybrid + rerank; returns formatted evidence for the agent loop."""
    orch = _orchestrator(config)
    bundle = orch.retrieve_core(
        query,
        history=history,
        expand_variants=EXPAND_VARIANTS_FULL,
        keep=SEARCH_VAULT_KEEP,
        on_status=on_status,
    )
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
        try:
            bundle = orch.retrieve_core(
                sub_query,
                history=history,
                expand_variants=EXPAND_VARIANTS_NONE,
                keep=SEARCH_VAULT_MANY_KEEP,
                on_status=on_status,
            )
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
            return idx, {
                "query": sub_query,
                "error": str(exc),
                "evidence": f"### {sub_query}\n\nSearch failed: {exc}",
                "trace_evidence": [],
            }

    with ThreadPoolExecutor(max_workers=len(cleaned)) as ex:
        futures = [ex.submit(_run_one, i, q) for i, q in enumerate(cleaned)]
        for fut in as_completed(futures):
            idx, payload = fut.result()
            results[idx] = payload

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
) -> dict[str, Any]:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(config.vault_root)
    from search_retrieval import search_transcript_evidence

    from _bootstrap import resolve_vault_root

    root = resolve_vault_root(config.vault_root)
    chunks_path = root / "catalog" / "chunks.jsonl"
    result = search_transcript_evidence(query, k, chunks_path=chunks_path, root=root)
    hits = result.get("hits") or []
    lines = [
        "Transcript hits (cite only from this block; use [ep-NNNN]):",
        "",
    ]
    trace_evidence: list[dict[str, Any]] = []
    for i, hit in enumerate(hits, start=1):
        ep = hit.get("episode_id", "")
        lines.append(
            f"#### Hit {i} — {hit.get('chunk_id', '')} [{ep}]\n"
            f"Section: {hit.get('section', '')}\n\n{hit.get('excerpt', '')}\n"
        )
        trace_evidence.append(
            {
                "chunk_id": hit.get("chunk_id", ""),
                "episode_id": ep,
                "section": hit.get("section", ""),
            }
        )
    evidence = "\n".join(lines) if hits else "No transcript hits for this query."
    return {
        "query": query,
        "evidence": evidence,
        "meta": result.get("meta") or {},
        "trace_evidence": trace_evidence,
    }
