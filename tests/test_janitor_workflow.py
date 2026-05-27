"""Janitor workflow helpers (catalog resolve, LLM clean mocked)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parent.parent

from janitor_workflow import (  # noqa: E402
    build_clean_user_message,
    draft_excerpt,
    load_janitor_clean_prompt,
    llm_clean_pasted_notes,
    resolve_catalog_row,
    run_reindex,
)

NAVAL_PASTE = """191 naval
* Context changes over time, interpretations will change (5:00)
* Labor leverage and capital leverage (16:00)
"""

NAVAL_LLM_OUT = """## Raw datapoints

- 5:00 — Context changes over time, interpretations will change
- 16:00 — Labor leverage and capital leverage
"""


def test_load_janitor_clean_prompt():
    text = load_janitor_clean_prompt()
    assert "Raw datapoints" in text
    assert "inconsistent" in text.lower() or "messy" in text.lower()


def test_build_clean_user_message_includes_episode():
    msg = build_clean_user_message(
        NAVAL_PASTE,
        episode_id="ep-0191",
        episode_title="Naval Ravikant",
    )
    assert "ep-0191" in msg
    assert "Naval Ravikant" in msg
    assert "191 naval" in msg


def test_build_clean_user_message_includes_feedback():
    msg = build_clean_user_message(
        NAVAL_PASTE,
        episode_id="ep-0191",
        current_draft=NAVAL_LLM_OUT,
        feedback="Fix 5:00 bullet to mention intent",
    )
    assert "User revision request" in msg
    assert "Fix 5:00 bullet" in msg
    assert "Current cleaned draft" in msg


def test_resolve_catalog_row_ep_0100():
    row = resolve_catalog_row(REPO, "ep-0100")
    assert row["id"] == "ep-0100"
    assert row.get("episode_number") == 100


def test_draft_excerpt_missing_draft():
    row = resolve_catalog_row(REPO, "ep-0400")
    text = draft_excerpt(REPO, row)
    assert "no draft" in text.lower()


@patch("expand_llm.call_openrouter")
def test_llm_clean_naval_paste(mock_call):
    mock_call.return_value = SimpleNamespace(content=NAVAL_LLM_OUT)
    body, warnings = llm_clean_pasted_notes(
        NAVAL_PASTE,
        api_key="test",
        model="test/model",
        vault_root=REPO,
        episode_id="ep-0191",
        episode_title="Naval Ravikant",
    )
    assert "- 5:00 — Context changes" in body
    assert "- 16:00 — Labor" in body
    assert body.startswith("## Raw datapoints")
    mock_call.assert_called_once()
    call_kwargs = mock_call.call_args.kwargs
    assert call_kwargs["model"] == "test/model"
    assert "ep-0191" in call_kwargs["user"]


@patch("reindex_vault.reindex_vault")
def test_run_reindex_invokes_both_steps(mock_reindex):
    mock_reindex.return_value = (0, "Reindexed chunks and embeddings.")
    code, msg = run_reindex(REPO)
    assert code == 0
    assert "embeddings" in msg
    mock_reindex.assert_called_once_with(REPO)
