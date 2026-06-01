"""Hybrid retrieval orchestrator for Telegram Librarian (expand → search → rerank)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from paths import CHUNKS_PATH, EMBEDDINGS_MANIFEST_PATH, EMBEDDINGS_PATH, ROOT
from rerank_llm import rerank_candidates
from search_retrieval import (
    _hybrid_search_parent_chunks,
    embed_queries,
    is_studied_chunk,
    merge_rrf_chunk_lists,
    search_transcript_keyword,
)

PROMPT_EXPAND_PATH = Path(__file__).resolve().parents[1] / "prompts" / "query_expand.md"

QUOTE_INTENT_RE = re.compile(
    r"\b(what did (he|she|they) say|exact words?|verbatim|quote from)\b",
    re.IGNORECASE,
)
EPISODE_REF_RE = re.compile(r"\bep-\d{4}\b", re.IGNORECASE)
GUEST_SIGNAL_RE = re.compile(r"\b(episode\s+)?\d{1,4}\b|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+")

RERANK_POOL_CAP = 40
RERANK_KEEP = 12
RERANK_SCORE_FALLBACK_THRESHOLD = 6.0


@dataclass
class EvidenceChunk:
    chunk_id: str
    episode_id: str
    title: str
    section: str
    excerpt: str
    rerank_score: float
    source_path: str
    rationale: str = ""


@dataclass
class EvidenceBundle:
    chunks: list[EvidenceChunk] = field(default_factory=list)
    retrieval_meta: dict[str, Any] = field(default_factory=dict)
    skip_retrieval: bool = False


@dataclass
class OrchestratorConfig:
    vault_root: Path
    model: str
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    chunks_path: Path | None = None
    embeddings_path: Path | None = None
    manifest_path: Path | None = None
    search_k: int = 8


def _paths(cfg: OrchestratorConfig) -> tuple[Path, Path, Path, Path]:
    root = cfg.vault_root
    if root != ROOT:
        return (
            cfg.chunks_path or root / "catalog" / "chunks.jsonl",
            cfg.embeddings_path or root / "catalog" / "embeddings.npy",
            cfg.manifest_path or root / "catalog" / "embeddings-manifest.jsonl",
            root,
        )
    return (
        cfg.chunks_path or CHUNKS_PATH,
        cfg.embeddings_path or EMBEDDINGS_PATH,
        cfg.manifest_path or EMBEDDINGS_MANIFEST_PATH,
        root,
    )


def classify_intent(user_message: str, history: list[dict[str, Any]] | None) -> str:
    msg = user_message.strip()
    lower = msg.lower()
    if msg.startswith("/"):
        return "meta"
    if lower in {"hi", "hello", "hey", "thanks", "thank you"}:
        return "meta"
    if any(p in lower for p in ("what model", "how many episodes", "which model")):
        return "meta"
    if history:
        recent = [m for m in history if m.get("role") == "assistant"][-1:]
        if recent and len(msg) < 120:
            if not EPISODE_REF_RE.search(msg) and not GUEST_SIGNAL_RE.search(msg):
                return "follow_up"
    return "thematic"


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in expand response")
    return json.loads(text[start : end + 1])


def expand_query_llm(
    user_message: str,
    *,
    history: list[dict[str, Any]] | None,
    model: str,
    api_key: str,
    base_url: str | None,
) -> tuple[str, list[str]]:
    system = PROMPT_EXPAND_PATH.read_text(encoding="utf-8").strip()
    turns = ""
    if history:
        tail = history[-4:]
        parts = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in tail]
        turns = "Recent turns:\n" + "\n".join(parts) + "\n\n"
    user = f"{turns}User message:\n{user_message.strip()}"

    from openrouter_client import call_openrouter

    result = call_openrouter(
        system=system,
        user=user,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    payload = _extract_json_object(result.content)
    standalone = str(payload.get("standalone_query") or user_message).strip()
    variants = payload.get("variants") or []
    cleaned = [str(v).strip() for v in variants if str(v).strip()]
    while len(cleaned) < 5:
        cleaned.append(standalone)
    return standalone, cleaned[:5]


def quote_intent(query: str) -> bool:
    return bool(QUOTE_INTENT_RE.search(query))


def chunk_for_rerank(ch: dict[str, Any], *, root: Path) -> dict[str, Any]:
    from search_retrieval import load_chunk_source_excerpt

    excerpt = (ch.get("excerpt") or "").strip()
    if len(excerpt) < 200:
        excerpt = load_chunk_source_excerpt(ch, max_chars=600, root=root)
    return {
        "chunk_id": ch.get("chunk_id", ""),
        "id": ch.get("id", ""),
        "title": ch.get("title", ""),
        "section": ch.get("section", ""),
        "excerpt": excerpt[:600],
        "source_path": ch.get("source_path", ""),
    }


def evidence_chunk_from_dict(ch: dict[str, Any]) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=str(ch.get("chunk_id", "")),
        episode_id=str(ch.get("id") or ch.get("episode_id", "")),
        title=str(ch.get("title") or ""),
        section=str(ch.get("section") or ""),
        excerpt=str(ch.get("excerpt") or "")[:1200],
        rerank_score=float(ch.get("rerank_score") or 0.0),
        source_path=str(ch.get("source_path") or ""),
        rationale=str(ch.get("rerank_rationale") or ""),
    )


def format_evidence_for_synthesis(bundle: EvidenceBundle) -> str:
    """User-message appendix with citable evidence (expanded + transcript only)."""
    if bundle.skip_retrieval or not bundle.chunks:
        return ""
    lines = [
        "---",
        "Retrieved evidence (cite only from this block; use [ep-NNNN]):",
        "",
    ]
    for i, ch in enumerate(bundle.chunks, start=1):
        lines.append(
            f"### Evidence {i} — {ch.chunk_id} [{ch.episode_id}]\n"
            f"Title: {ch.title}\nSection: {ch.section}\n\n{ch.excerpt}\n"
        )
    return "\n".join(lines)


class RetrievalOrchestrator:
    def __init__(
        self,
        config: OrchestratorConfig,
        *,
        expand_fn: Callable[..., tuple[str, list[str]]] | None = None,
        rerank_fn: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        self.config = config
        self._expand_fn = expand_fn
        self._rerank_fn = rerank_fn

    def retrieve(
        self,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> EvidenceBundle:
        intent = classify_intent(user_message, history)
        meta: dict[str, Any] = {"intent": intent}

        if intent == "meta":
            meta["skip_reason"] = "meta_intent"
            return EvidenceBundle(chunks=[], retrieval_meta=meta, skip_retrieval=True)

        cfg = self.config
        chunks_path, emb_path, man_path, vault_root = _paths(cfg)

        if on_status:
            on_status("Expanding query…")
        expand = self._expand_fn or expand_query_llm
        standalone, variants = expand(
            user_message,
            history=history,
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
        )
        meta["standalone_query"] = standalone
        meta["variants"] = variants

        if on_status:
            on_status("Searching vault…")
        vectors = embed_queries(variants)
        per_variant: list[list[dict[str, Any]]] = []
        pool_k = max(cfg.search_k * 4, 32)
        for variant, qvec in zip(variants, vectors):
            hits = _hybrid_search_parent_chunks(
                variant,
                pool_k,
                chunks_path=chunks_path,
                embeddings_path=emb_path,
                manifest_path=man_path,
                query_vector=qvec,
                root=vault_root,
            )
            per_variant.append(hits)

        merged = merge_rrf_chunk_lists(
            per_variant,
            cap=RERANK_POOL_CAP,
            root=vault_root,
        )
        meta["candidate_count"] = len(merged)

        if on_status:
            on_status("Ranking results…")
        rerank_input = [chunk_for_rerank(ch, root=vault_root) for ch in merged]
        rerank = self._rerank_fn or rerank_candidates
        ranked = rerank(
            standalone,
            rerank_input,
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
        )

        top_scores = [float(ch.get("rerank_score") or 0) for ch in ranked[:RERANK_KEEP]]
        meta["reranked_top5_scores"] = top_scores[:5]
        max_score = max(top_scores) if top_scores else 0.0

        fallback = max_score < RERANK_SCORE_FALLBACK_THRESHOLD or quote_intent(standalone)
        meta["fallback_triggered"] = fallback

        if fallback:
            tx_hits = search_transcript_keyword(
                standalone,
                3,
                chunks_path=chunks_path,
                root=vault_root,
            )
            if variants:
                tx_hits.extend(
                    search_transcript_keyword(
                        variants[0],
                        3,
                        chunks_path=chunks_path,
                        root=vault_root,
                    )
                )
            seen: set[str] = set()
            extra: list[dict[str, Any]] = []
            for ch in tx_hits:
                cid = ch.get("chunk_id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                extra.append(chunk_for_rerank(ch, root=vault_root))
            if extra:
                ranked = rerank(
                    standalone,
                    rerank_input + extra,
                    model=cfg.model,
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                )

        citable: list[EvidenceChunk] = []
        for ch in ranked:
            section = str(ch.get("section") or "")
            if section.startswith("summary:"):
                continue
            if not section.startswith(("expanded:", "transcript:")):
                continue
            citable.append(evidence_chunk_from_dict(ch))
            if len(citable) >= RERANK_KEEP:
                break

        meta["studied_filter_applied"] = True
        meta["embed_present"] = emb_path.is_file() and man_path.is_file()
        return EvidenceBundle(chunks=citable, retrieval_meta=meta, skip_retrieval=False)


def orchestrator_from_agent_config(agent_config: Any) -> RetrievalOrchestrator:
    return RetrievalOrchestrator(
        OrchestratorConfig(
            vault_root=agent_config.vault_root,
            model=agent_config.model,
            api_key=agent_config.api_key,
            base_url=getattr(agent_config, "openrouter_base_url", "https://openrouter.ai/api/v1"),
            search_k=getattr(agent_config, "default_search_k", 8),
        )
    )
