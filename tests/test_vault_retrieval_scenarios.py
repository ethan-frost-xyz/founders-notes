"""Scenario-driven retrieval tests against catalog/chunks.jsonl (no live API)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent

from config import AgentConfig  # noqa: E402

SCENARIOS_PATH = Path(__file__).parent / "fixtures" / "vault_retrieval_scenarios.jsonl"
CHUNKS_PATH = REPO / "catalog" / "chunks.jsonl"
PRE_FILTER_CHUNK_CEILING = 8226


def _load_scenarios() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in SCENARIOS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _scenario_id(row: dict[str, Any]) -> str:
    return str(row["id"])


def _run_scenario(
    row: dict[str, Any],
    *,
    agent_config: AgentConfig,
) -> dict[str, Any]:
    from search_test_helpers import run_parent_search, run_transcript_search

    tool = str(row["tool"])
    query = str(row["query"])
    k = int(row.get("k") or 8)
    vault_root = agent_config.vault_root
    if tool == "search_vault_parent":
        return run_parent_search(query, k=k, vault_root=vault_root)
    if tool == "search_transcript":
        return run_transcript_search(query, k=k, vault_root=vault_root)
    raise ValueError(f"unsupported scenario tool: {tool}")


@pytest.mark.parametrize("row", _load_scenarios(), ids=_scenario_id)
def test_vault_retrieval_scenario(
    row: dict[str, Any],
    agent_config: AgentConfig,
) -> None:
    if row.get("needs_rebuild") and os.getenv("RUN_REBUILT_INDEX_SCENARIOS") != "1":
        pytest.skip("rebuilt index scenarios require RUN_REBUILT_INDEX_SCENARIOS=1")

    result = _run_scenario(row, agent_config=agent_config)
    hits = result.get("hits") or []

    if "expect_max_hits" in row:
        max_hits = int(row["expect_max_hits"])
        ep_id = row.get("episode_id")
        if ep_id:
            hits = [h for h in hits if h.get("episode_id") == ep_id]
        assert len(hits) <= max_hits, (
            f"{row['id']}: expected <= {max_hits} hits, got {len(hits)}: {hits[:3]}"
        )
        return

    assert hits, f"{row['id']}: expected at least one hit"
    top = hits[0]
    if row.get("expect_top_episode"):
        assert top.get("episode_id") == row["expect_top_episode"], (
            f"{row['id']}: top episode {top.get('episode_id')!r}"
        )
    if row.get("expect_section_prefix"):
        section = top.get("section") or ""
        assert section.startswith(row["expect_section_prefix"]), (
            f"{row['id']}: section {section!r}"
        )
    if row.get("expect_excerpt_contains"):
        needle = row["expect_excerpt_contains"].lower()
        excerpt = (top.get("excerpt") or "").lower()
        assert needle in excerpt, f"{row['id']}: excerpt missing {needle!r}"


def test_chunk_count_after_listen_filter() -> None:
    """Un-listened transcript exclusion should shrink the index materially."""
    if os.getenv("RUN_FULL_INDEX_SCENARIOS") != "1":
        pytest.skip("full catalog/chunks.jsonl check requires RUN_FULL_INDEX_SCENARIOS=1")
    assert CHUNKS_PATH.is_file(), "catalog/chunks.jsonl missing; run build_chunks.py"
    count = sum(1 for line in CHUNKS_PATH.open(encoding="utf-8") if line.strip())
    assert count < PRE_FILTER_CHUNK_CEILING, (
        f"expected fewer than {PRE_FILTER_CHUNK_CEILING} chunks after filter, got {count}"
    )
    assert count < 5000, f"expected focused index under 5000 chunks, got {count}"
