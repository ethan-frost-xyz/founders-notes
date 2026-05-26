"""Tests for ingestion/maintain.py (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import paths

# Import after conftest path setup
import maintain


def _catalog_row(ep_id: str, num: int, slug: str | None = None) -> dict:
    return {
        "id": ep_id,
        "slug": slug or f"{num}-test",
        "episode_number": num,
        "title": "T",
        "transcript_status": "complete",
        "founders_url": f"https://www.founderspodcast.com/episodes/{num}",
        "colossus_url": "https://example.com/colossus",
    }


def test_refresh_coverage_report_writes_gaps(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    gaps_path = tmp_path / "catalog" / "gaps.md"
    monkeypatch.setattr(paths, "GAPS_PATH", gaps_path)
    import gaps_report

    monkeypatch.setattr(gaps_report, "GAPS_PATH", gaps_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(paths, "POSTS_DIR", tmp_path / "content" / "posts")

    rows = [_catalog_row("ep-0001", 1)]
    (tmp_path / "catalog").mkdir(parents=True)
    stats, blocking = maintain.refresh_coverage_report(rows)
    assert stats.catalog_rows == 1
    assert (tmp_path / "catalog" / "gaps.md").exists()
    assert blocking  # < 400 rows triggers blocking message


def test_find_next_notes_path(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")

    rows = [
        _catalog_row("ep-0190", 190),
        _catalog_row("ep-0191", 191),
    ]
    # ep-0190 has datapoints
    n190 = paths.notes_file_path("ep-0190", "190-test", 190)
    n190.parent.mkdir(parents=True)
    n190.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )
    # ep-0191 missing file
    path = maintain.find_next_notes_path(rows, episode_from=190)
    assert path is not None
    assert path == paths.notes_file_path("ep-0191", "191-test", 191)


def test_collect_production_drafts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")

    row = _catalog_row("ep-0001", 1)
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — a\n",
        encoding="utf-8",
    )
    draft = paths.expanded_draft_file_path("ep-0001", "1-test", 1)
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(
        "---\n---\n\n## Expanded datapoints\n\n### 1:00 — a\n\nContext: c\n\n"
        'Quote: **x** (1:00)\n\nKey takeaway: y\n',
        encoding="utf-8",
    )

    summaries = maintain.collect_production_drafts([row])
    assert len(summaries) == 1
    assert summaries[0].episode_id == "ep-0001"
    assert summaries[0].n_errors == 0


def test_select_promote_all_ready(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")

    rows = [_catalog_row("ep-0001", 1), _catalog_row("ep-0002", 2)]
    draft = paths.expanded_draft_file_path("ep-0001", "1-test", 1)
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("---\n---\n\n## Expanded datapoints\n", encoding="utf-8")

    selected = maintain._select_promote_rows(
        rows, episode_id=None, episode_from=None, episode_to=None, all_ready=True
    )
    assert len(selected) == 1
    assert selected[0]["id"] == "ep-0001"


def test_select_expand_missing_expanded(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")

    row = _catalog_row("ep-0001", 1)
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )
    txdir = paths.transcript_dir("ep-0001", "1-test", 1)
    txdir.mkdir(parents=True)
    (txdir / paths.transcript_filename("ep-0001", "1-test", 1)).write_text(
        "---\n---\n\nbody\n",
        encoding="utf-8",
    )

    selected = maintain._select_expand(
        [row],
        episode_id=None,
        episode_from=None,
        episode_to=None,
        missing_expanded=True,
        limit=5,
    )
    assert len(selected) == 1
    assert selected[0]["id"] == "ep-0001"


@patch("expand_datapoints_llm.run_expand_one")
def test_run_expand_batch_dry_run(mock_expand, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")

    row = _catalog_row("ep-0001", 1)
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )
    txdir = paths.transcript_dir("ep-0001", "1-test", 1)
    txdir.mkdir(parents=True)
    (txdir / paths.transcript_filename("ep-0001", "1-test", 1)).write_text(
        "---\n---\n\nbody\n",
        encoding="utf-8",
    )

    prompt = tmp_path / "ingestion" / "prompts" / "expand_datapoints.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text(
        "<<<SYSTEM>>>\ns\n<<<USER>>>\n{notes}\n{transcript}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "maintain.default_prompt_path",
        lambda: prompt,
    )

    maintain._run_expand_batch([row], dry_run=True, force=False, subprocess_per_episode=False)
    mock_expand.assert_not_called()


def test_tune_namespace_defaults():
    ns = maintain._tune_namespace()
    assert ns.run_id == maintain.DEFAULT_TUNE_RUN_ID
    assert ns.batch_file == maintain.DEFAULT_TUNE_BATCH


def test_build_all_chunks_helper(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "CHUNKS_PATH", tmp_path / "catalog" / "chunks.jsonl")
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(paths, "POSTS_DIR", tmp_path / "content" / "posts")

    from build_chunks import build_all_chunks

    row = _catalog_row("ep-0001", 1)
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\ntitle: T\ncontent_type: notes\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n",
        encoding="utf-8",
    )

    n = build_all_chunks([row])
    assert n >= 1
    lines = (tmp_path / "catalog" / "chunks.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == n
    first = json.loads(lines[0])
    assert first["id"] == "ep-0001"
