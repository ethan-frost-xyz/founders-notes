"""Tests for Librarian evidence formatting helpers."""

from __future__ import annotations

from evidence_format import format_load_episode_for_tool


def test_format_load_episode_strips_frontmatter_and_surfaces_listened():
    payload = {
        "episode_id": "ep-0016",
        "sections": {
            "expanded": (
                "---\n"
                "id: ep-0016\n"
                "title: Rockefeller\n"
                "---\n\n"
                "### 10:00 — Competition\n\nQuote: competition is a sin."
            ),
        },
        "meta": {
            "listened": True,
            "title": "#16 Rockefeller",
            "has_expanded": True,
            "has_post": False,
        },
    }
    text = format_load_episode_for_tool(payload)
    assert "### Episode ep-0016 — #16 Rockefeller" in text
    assert "Listened: true" in text
    assert "id: ep-0016" not in text
    assert "competition is a sin" in text
    assert "[ep-NNNN]" in text
    assert "#### expanded" in text


def test_format_load_episode_orders_sections():
    payload = {
        "episode_id": "ep-0001",
        "sections": {
            "post": "post body",
            "expanded": "expanded body",
            "notes": "notes body",
        },
        "meta": {"listened": False, "title": "Test"},
    }
    text = format_load_episode_for_tool(payload)
    assert text.index("#### expanded") < text.index("#### notes") < text.index("#### post")


def test_format_load_episode_empty_sections():
    payload = {
        "episode_id": "ep-9999",
        "sections": {},
        "meta": {"listened": False, "title": "Empty"},
    }
    text = format_load_episode_for_tool(payload)
    assert "No on-disk sections available" in text
