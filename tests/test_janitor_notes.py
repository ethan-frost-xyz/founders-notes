"""Janitor episode parsing and finalize helpers (LLM clean is separate)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOT = REPO / "services" / "telegram" / "bot"
if str(BOT) not in sys.path:
    sys.path.insert(0, str(BOT))

from janitor_notes import finalize_notes_body, merge_notes_body, parse_episode_id  # noqa: E402


def test_parse_episode_id_formats():
    assert parse_episode_id("200") == "ep-0200"
    assert parse_episode_id("ep-0200") == "ep-0200"
    assert parse_episode_id("episode 417") == "ep-0417"
    assert parse_episode_id("191 naval") == "ep-0191"
    assert parse_episode_id("no episode here") is None


def test_finalize_notes_body_wraps_llm_bullets():
    body, warnings = finalize_notes_body("- 5:00 — hook\n- 8:00 — other")
    assert body.startswith("## Raw datapoints")
    assert "- 5:00 — hook" in body
    assert not any("missing" in w.lower() for w in warnings)


def test_finalize_notes_body_warns_empty():
    body, warnings = finalize_notes_body("   ")
    assert warnings
    assert "Empty" in warnings[0]


def test_merge_notes_appends_bullets():
    existing = "## Raw datapoints\n\n- 1:00 — first\n"
    new = "## Raw datapoints\n\n- 2:00 — second\n"
    merged = merge_notes_body(existing, new)
    assert "- 1:00 — first" in merged
    assert "- 2:00 — second" in merged
