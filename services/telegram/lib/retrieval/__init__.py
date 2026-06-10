"""Telegram Librarian retrieval orchestration (expand → hybrid → rerank)."""

from evidence_format import format_evidence_for_tool

from .orchestrator import (
    EXPAND_VARIANTS_FULL,
    EXPAND_VARIANTS_NONE,
    SEARCH_VAULT_KEEP,
    SEARCH_VAULT_MANY_KEEP,
    SEARCH_VAULT_MANY_MAX,
    EvidenceBundle,
    EvidenceChunk,
    OrchestratorConfig,
    RetrievalOrchestrator,
    evidence_meta_for_trace,
    orchestrator_from_agent_config,
    quote_intent,
)

__all__ = [
    "EXPAND_VARIANTS_FULL",
    "EXPAND_VARIANTS_NONE",
    "SEARCH_VAULT_KEEP",
    "SEARCH_VAULT_MANY_KEEP",
    "SEARCH_VAULT_MANY_MAX",
    "EvidenceBundle",
    "EvidenceChunk",
    "OrchestratorConfig",
    "RetrievalOrchestrator",
    "evidence_meta_for_trace",
    "format_evidence_for_tool",
    "orchestrator_from_agent_config",
    "quote_intent",
]
