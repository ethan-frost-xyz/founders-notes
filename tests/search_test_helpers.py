"""Helpers for vault search tests (direct search_retrieval API, not vault.py wrappers)."""

from __future__ import annotations

from pathlib import Path


def run_parent_search(query: str, *, k: int = 8, vault_root: Path) -> dict:
    from paths import catalog_paths
    from search_retrieval import search_parent_evidence

    cp = catalog_paths(vault_root)
    return search_parent_evidence(
        query,
        k,
        chunks_path=cp.chunks,
        embeddings_path=cp.embeddings,
        manifest_path=cp.embeddings_manifest,
        root=cp.root,
    )


def run_transcript_search(query: str, *, k: int = 8, vault_root: Path) -> dict:
    from paths import catalog_paths
    from search_retrieval import search_transcript_evidence

    cp = catalog_paths(vault_root)
    return search_transcript_evidence(
        query,
        k,
        chunks_path=cp.chunks,
        root=cp.root,
    )
