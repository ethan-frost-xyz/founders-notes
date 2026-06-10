"""Tests for Librarian evidence formatting helpers."""

from __future__ import annotations

from evidence_format import (
    format_evidence_for_tool,
    format_load_episode_for_tool,
    format_search_evidence,
    format_transcript_evidence,
    trace_evidence_from_hits,
)
from retrieval.orchestrator import EvidenceBundle  # noqa: E402


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


def test_format_search_evidence_empty_with_label():
    text = format_search_evidence([], label="Edison teams")
    assert "Edison teams" in text
    assert "No citable evidence" in text


def test_format_search_evidence_includes_chunk_fields():
    text = format_search_evidence(
        [
            {
                "chunk_id": "expanded:ep-0001:ctx",
                "episode_id": "ep-0001",
                "title": "Test Episode",
                "section": "expanded:context",
                "excerpt": "Key insight here.",
                "rerank_score": 8.5,
            }
        ]
    )
    assert "#### Evidence 1 — expanded:ep-0001:ctx [ep-0001]" in text
    assert "Title: Test Episode" in text
    assert "Score: 8.5" in text
    assert "Key insight here." in text
    assert "[ep-NNNN]" in text


def test_format_transcript_evidence_empty():
    assert format_transcript_evidence([]) == "No transcript hits for this query."


def test_format_transcript_evidence_hit_shape():
    text = format_transcript_evidence(
        [
            {
                "chunk_id": "transcript:ep-0002:seg",
                "episode_id": "ep-0002",
                "section": "transcript:dialogue",
                "excerpt": "Verbatim line.",
            }
        ]
    )
    assert "#### Hit 1 — transcript:ep-0002:seg [ep-0002]" in text
    assert "Section: transcript:dialogue" in text
    assert "Verbatim line." in text


def test_trace_evidence_from_hits():
    hits = [
        {
            "chunk_id": "c1",
            "episode_id": "ep-0003",
            "section": "expanded:quote",
            "excerpt": "ignored",
        }
    ]
    assert trace_evidence_from_hits(hits) == [
        {
            "chunk_id": "c1",
            "episode_id": "ep-0003",
            "section": "expanded:quote",
        }
    ]


def test_format_evidence_for_tool_labels_subquery():
    bundle = EvidenceBundle(
        chunks=[],
        retrieval_meta={},
    )
    text = format_evidence_for_tool(bundle, label="Edison teams")
    assert "Edison teams" in text
    assert "No citable evidence" in text
