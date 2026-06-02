"""Telegram adapter for ingestion retrieval orchestrator."""

from __future__ import annotations

from typing import Any, Callable

from config import AgentConfig
from retrieval_orchestrator import EvidenceBundle, RetrievalOrchestrator, orchestrator_from_agent_config


def retrieve_for_turn(
    user_message: str,
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> EvidenceBundle:
    from _bootstrap import setup_ingestion_paths

    setup_ingestion_paths(config.vault_root)
    from runtime_settings import effective_retrieval_model

    retrieval_model, _ = effective_retrieval_model()
    orchestrator = orchestrator_from_agent_config(config, retrieval_model=retrieval_model)
    return orchestrator.retrieve(user_message, history=history, on_status=on_status)
