"""Neutral cache invalidation for vault search (breaks catalog ↔ retrieval cycle)."""

from __future__ import annotations


def invalidate_all_search_caches() -> None:
    """Clear studied-episode and chunk-index caches after catalog/chunks writes."""
    from search_studied import invalidate_studied_episode_cache

    invalidate_studied_episode_cache()
