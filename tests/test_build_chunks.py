"""Unit tests for catalog chunk indexing (listened filter, line numbers, expanded splits)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_chunks import (  # noqa: E402
    body_start_line_in_file,
    build_all_chunks,
    chunk_expanded_datapoints,
    episode_is_listened,
)
from paths import notes_file_path  # noqa: E402


def test_episode_is_listened_empty_scaffold(tmp_path: Path):
    npath = tmp_path / "ep.notes.md"
    npath.write_text(
        "---\ntitle: T\ncontent_type: notes\n---\n\n## Raw datapoints\n\n"
        "<!-- Add bullets here -->\n",
        encoding="utf-8",
    )
    assert episode_is_listened(npath) is False


def test_episode_is_listened_timestamp_bullet(tmp_path: Path):
    npath = tmp_path / "ep.notes.md"
    npath.write_text(
        "---\ntitle: T\ncontent_type: notes\n---\n\n## Raw datapoints\n\n"
        "- 1:23:45 — hook\n",
        encoding="utf-8",
    )
    assert episode_is_listened(npath) is True


def test_body_start_line_in_file():
    raw = "---\nid: x\n---\n\n## Section\n\nline\n"
    assert body_start_line_in_file(raw) == 5


def test_chunk_expanded_datapoints_splits_on_headings():
    body = (
        "### 09:30 — First\n\nQuote one.\n\n"
        "### 12:00 — Second\n\nQuote two.\n"
    )
    line_offset = 14
    chunks = chunk_expanded_datapoints(
        "ep-0001",
        "expanded:expanded_datapoints",
        body,
        "notes/ep.expanded.md",
        {"title": "T"},
        line_offset=line_offset,
    )
    assert len(chunks) == 2
    assert chunks[0]["start_line"] == line_offset + 1
    assert "First" in chunks[0]["excerpt"]
    assert chunks[1]["start_line"] > chunks[0]["start_line"]
    assert "Second" in chunks[1]["excerpt"]


def test_build_all_chunks_skips_transcript_when_unlistened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "CHUNKS_PATH", tmp_path / "catalog" / "chunks.jsonl")
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(paths, "POSTS_DIR", tmp_path / "content" / "posts")

    row = {
        "id": "ep-0999",
        "slug": "999-test",
        "episode_number": 999,
        "title": "#999 Test",
    }
    npath = notes_file_path("ep-0999", "999-test", 999)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\ntitle: T\ncontent_type: notes\n---\n\n## Raw datapoints\n",
        encoding="utf-8",
    )
    tx_dir = tmp_path / "content" / "transcripts" / "ep-0999-999-test"
    tx_dir.mkdir(parents=True)
    tx_path = tx_dir / "ep-0999-999-test.transcript.md"
    tx_path.write_text(
        "---\ntitle: T\ncontent_type: transcript\n---\n\n"
        "## Body\n\nTranscript line about noise.\n",
        encoding="utf-8",
    )

    n = build_all_chunks([row])
    lines = (tmp_path / "catalog" / "chunks.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert n == len(lines)
    sections = {json.loads(line)["section"] for line in lines}
    assert not any(s.startswith("transcript:") for s in sections)
