"""Hybrid retrieval orchestrator for Telegram Librarian (expand → search → rerank)."""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from paths import CHUNKS_PATH, EMBEDDINGS_MANIFEST_PATH, EMBEDDINGS_PATH, ROOT
from rerank_llm import rerank_candidates
from search_retrieval import (
    ChunkIndex,
    _hybrid_search_parent_chunks,
    embed_queries,
    get_chunk_index,
    get_embedding_store,
    is_studied_chunk,
    merge_rrf_chunk_lists,
    search_transcript_keyword,
)

PROMPT_EXPAND_PATH = Path(__file__).resolve().parents[1] / "prompts" / "query_expand.md"

QUOTE_INTENT_RE = re.compile(
    r"\b(what did (he|she|they) say|exact words?|verbatim|quote from)\b",
    re.IGNORECASE,
)

RERANK_POOL_CAP = 40
RERANK_KEEP = 12
SEARCH_VAULT_KEEP = 8
SEARCH_VAULT_MANY_KEEP = 5
SEARCH_VAULT_MANY_MAX = 6
EXPAND_VARIANTS_FULL = 5
EXPAND_VARIANTS_NONE = 0
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
    while len(cleaned) < EXPAND_VARIANTS_FULL:
        cleaned.append(standalone)
    return standalone, cleaned[:EXPAND_VARIANTS_FULL]


def quote_intent(query: str) -> bool:
    return bool(QUOTE_INTENT_RE.search(query))


def _search_one_variant(
    args: tuple[str, Any, int, Path, Path, Path, Path, ChunkIndex],
) -> list[dict[str, Any]]:
    variant, qvec, pool_k, chunks_path, emb_path, man_path, vault_root, index = args
    return _hybrid_search_parent_chunks(
        variant,
        pool_k,
        chunks_path=chunks_path,
        embeddings_path=emb_path,
        manifest_path=man_path,
        query_vector=qvec,
        root=vault_root,
        index=index,
    )


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


def evidence_meta_for_trace(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    """Compact episode_ids + rerank scores for tool_trace."""
    return [
        {
            "chunk_id": ch.chunk_id,
            "episode_id": ch.episode_id,
            "rerank_score": ch.rerank_score,
            "section": ch.section,
        }
        for ch in bundle.chunks
    ]


def format_evidence_for_tool(
    bundle: EvidenceBundle,
    *,
    label: str | None = None,
    max_chunks: int = SEARCH_VAULT_KEEP,
) -> str:
    """Readable evidence block returned from search_vault / search_vault_many."""
    if not bundle.chunks:
        header = f"### {label}\n" if label else ""
        return f"{header}No citable evidence found for this query."

    lines: list[str] = []
    if label:
        lines.append(f"### {label}")
        lines.append("")
    lines.append("Retrieved evidence (cite only from this block; use [ep-NNNN]):")
    lines.append("")
    for i, ch in enumerate(bundle.chunks[:max_chunks], start=1):
        lines.append(
            f"#### Evidence {i} — {ch.chunk_id} [{ch.episode_id}]\n"
            f"Title: {ch.title}\nSection: {ch.section}\n"
            f"Score: {ch.rerank_score:.1f}\n\n{ch.excerpt}\n"
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

    def retrieve_core(
        self,
        query: str,
        *,
        history: list[dict[str, Any]] | None = None,
        expand_variants: int = EXPAND_VARIANTS_FULL,
        keep: int = SEARCH_VAULT_KEEP,
        on_status: Callable[[str], None] | None = None,
        on_timing: Callable[[str, int], None] | None = None,
    ) -> EvidenceBundle:
        """Expand → hybrid search → rerank → optional transcript fallback."""
        meta: dict[str, Any] = {"query": query.strip(), "expand_variants": expand_variants}
        cfg = self.config
        chunks_path, emb_path, man_path, vault_root = _paths(cfg)
        q = query.strip()

        if expand_variants <= EXPAND_VARIANTS_NONE:
            standalone, variants = q, [q]
            meta["expansion_skipped"] = True
        else:
            if on_status:
                on_status("Expanding query…")
            expand = self._expand_fn or expand_query_llm
            t0 = time.perf_counter()
            standalone, variants = expand(
                q,
                history=history,
                model=cfg.model,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
            )
            if on_timing:
                on_timing("retrieval_llm", int((time.perf_counter() - t0) * 1000))
            meta["expansion_skipped"] = False

        meta["standalone_query"] = standalone
        meta["variants"] = variants

        if on_status:
            on_status("Searching vault…")
        t_local = time.perf_counter()
        vectors = embed_queries(variants)
        pool_k = max(cfg.search_k * 4, 32)
        get_embedding_store(embeddings_path=emb_path, manifest_path=man_path)
        chunk_index = get_chunk_index(chunks_path=chunks_path, root=vault_root)
        search_args = [
            (variant, qvec, pool_k, chunks_path, emb_path, man_path, vault_root, chunk_index)
            for variant, qvec in zip(variants, vectors)
        ]
        with ThreadPoolExecutor(max_workers=max(1, len(variants))) as ex:
            per_variant = list(ex.map(_search_one_variant, search_args))
        if on_timing:
            on_timing("vault_local", int((time.perf_counter() - t_local) * 1000))

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
        t0 = time.perf_counter()
        ranked = rerank(
            standalone,
            rerank_input,
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
        )
        if on_timing:
            on_timing("retrieval_llm", int((time.perf_counter() - t0) * 1000))

        top_scores = [float(ch.get("rerank_score") or 0) for ch in ranked[:RERANK_KEEP]]
        meta["reranked_top5_scores"] = top_scores[:5]
        max_score = max(top_scores) if top_scores else 0.0

        fallback = max_score < RERANK_SCORE_FALLBACK_THRESHOLD or quote_intent(standalone)
        meta["fallback_triggered"] = fallback

        if fallback:
            t_tx = time.perf_counter()
            tx_hits = search_transcript_keyword(
                standalone,
                3,
                chunks_path=chunks_path,
                root=vault_root,
                index=chunk_index,
            )
            if variants:
                tx_hits.extend(
                    search_transcript_keyword(
                        variants[0],
                        3,
                        chunks_path=chunks_path,
                        root=vault_root,
                        index=chunk_index,
                    )
                )
            if on_timing:
                on_timing("vault_local", int((time.perf_counter() - t_tx) * 1000))
            seen: set[str] = set()
            extra: list[dict[str, Any]] = []
            for ch in tx_hits:
                cid = ch.get("chunk_id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                extra.append(chunk_for_rerank(ch, root=vault_root))
            if extra:
                t0 = time.perf_counter()
                ranked = rerank(
                    standalone,
                    rerank_input + extra,
                    model=cfg.model,
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                )
                if on_timing:
                    on_timing("retrieval_llm", int((time.perf_counter() - t0) * 1000))

        citable: list[EvidenceChunk] = []
        for ch in ranked:
            section = str(ch.get("section") or "")
            if section.startswith("summary:"):
                continue
            if not section.startswith(("expanded:", "transcript:")):
                continue
            citable.append(evidence_chunk_from_dict(ch))
            if len(citable) >= keep:
                break

        meta["studied_filter_applied"] = True
        meta["embed_present"] = emb_path.is_file() and man_path.is_file()
        meta["keep"] = keep
        return EvidenceBundle(chunks=citable, retrieval_meta=meta)

    def retrieve(
        self,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> EvidenceBundle:
        """Backward-compatible alias for retrieve_core with full expansion."""
        return self.retrieve_core(
            user_message,
            history=history,
            expand_variants=EXPAND_VARIANTS_FULL,
            keep=SEARCH_VAULT_KEEP,
            on_status=on_status,
        )


def orchestrator_from_agent_config(
    agent_config: Any,
    *,
    retrieval_model: str | None = None,
) -> RetrievalOrchestrator:
    """Build orchestrator; expand/rerank use retrieval_model when set, else agent model."""
    model = (retrieval_model or agent_config.model or "").strip() or agent_config.model
    return RetrievalOrchestrator(
        OrchestratorConfig(
            vault_root=agent_config.vault_root,
            model=model,
            api_key=agent_config.api_key,
            base_url=getattr(agent_config, "openrouter_base_url", "https://openrouter.ai/api/v1"),
            search_k=getattr(agent_config, "default_search_k", 8),
        )
    )
