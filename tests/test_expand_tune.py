"""Tests for expand_tune and staging paths (no network)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import paths
from expand_llm import write_expanded_draft
from expand_tune import build_child_cmd, load_batch_file, run_dir
from paths import staging_draft_file_path


def test_staging_draft_file_path(tmp_path: Path):
    root = tmp_path / "runs" / "tune-001"
    p = staging_draft_file_path(root, "A", "ep-0001", "1-test", 1)
    assert p == root / "A" / "ep-0001-test" / "ep-0001-test.expanded.draft.md"


def test_load_batch_file(tmp_path: Path):
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps({"episode_ids": ["ep-0001", "ep-0002"]}),
        encoding="utf-8",
    )
    assert load_batch_file(batch) == ["ep-0001", "ep-0002"]


def test_build_child_cmd_one_episode():
    cmd = build_child_cmd(
        episode_id="ep-0042",
        run_id="tune-001",
        variant="B",
        prompt_path=Path("/repo/ingestion/prompts/expand_datapoints.candidate.md"),
        apply=True,
        force=True,
        model="test/model",
    )
    assert cmd.count("--id") == 1
    assert "ep-0042" in cmd
    assert "--staging-dir" in cmd
    assert "tune-001" in " ".join(cmd)
    assert "--variant" in cmd and "B" in cmd
    assert "--prompt" in cmd
    assert "--apply" in cmd
    assert "--force" in cmd
    assert "--model" in cmd and "test/model" in cmd
    assert cmd[0] == sys.executable


def test_write_expanded_draft_staging(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    staging = tmp_path / "runs" / "r1"
    row = {"id": "ep-0001", "slug": "1-test", "episode_number": 1, "title": "T"}
    prompt = tmp_path / "p.md"
    prompt.write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{notes}\n{transcript}\n", encoding="utf-8")
    body = '## Expanded datapoints\n\n### 1:00 — x\n**Quote:** "a"\n**Takeaway:** b\n'
    out = write_expanded_draft(
        row,
        body,
        model="m",
        prompt_path=prompt,
        staging_root=staging,
        variant="A",
    )
    assert out == staging / "A" / "ep-0001-test" / "ep-0001-test.expanded.draft.md"
    assert out.exists()


@patch("expand_tune.subprocess.run")
def test_expand_subprocess_per_episode(mock_run, monkeypatch, tmp_path: Path):
    monkeypatch.setattr("expand_tune.paths.ROOT", tmp_path)
    monkeypatch.setattr("expand_tune.EXPAND_RUNS_DIR", tmp_path / "expand-runs")
    monkeypatch.setattr("expand_tune.DEFAULT_BATCH_FILE", tmp_path / "batch.json")
    monkeypatch.setattr("expand_tune.PROMPT_A", tmp_path / "a.md")
    monkeypatch.setattr("expand_tune.PROMPT_B", tmp_path / "b.md")
    (tmp_path / "a.md").write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{n}\n{t}\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{n}\n{t}\n", encoding="utf-8")
    (tmp_path / "batch.json").write_text(
        json.dumps({"episode_ids": ["ep-0001", "ep-0002"]}),
        encoding="utf-8",
    )
    manifest_dir = tmp_path / "expand-runs" / "r1"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps({"run_id": "r1", "batch_file": "batch.json", "variants": {}}),
        encoding="utf-8",
    )

    catalog = tmp_path / "catalog"
    catalog.mkdir()
    rows = [
        {
            "id": "ep-0001",
            "slug": "1-a",
            "episode_number": 1,
            "title": "A",
            "transcript_status": "complete",
        },
        {
            "id": "ep-0002",
            "slug": "2-b",
            "episode_number": 2,
            "title": "B",
            "transcript_status": "complete",
        },
    ]
    (catalog / "episodes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("expand_tune.paths.CATALOG_PATH", catalog / "episodes.jsonl")

    mock_run.return_value.returncode = 0

    from expand_tune import cmd_expand

    class Args:
        run_id = "r1"
        variant = "A"
        prompt = None
        model = None
        force = False
        dry_run = True
        apply = False
        batch_file = tmp_path / "batch.json"

    cmd_expand(Args())
    assert mock_run.call_count == 2
    for call in mock_run.call_args_list:
        cmd = call[0][0]
        assert cmd.count("--id") == 1


def test_draft_report_row_detects_validation(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr("expand_tune.EXPAND_RUNS_DIR", tmp_path / "expand-runs")

    row = {"id": "ep-0001", "slug": "1-test", "episode_number": 1, "title": "T"}
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — a\n- 2:00 — b\n",
        encoding="utf-8",
    )
    staging = run_dir("r1")
    prompt = tmp_path / "p.md"
    prompt.write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{n}\n{t}\n", encoding="utf-8")
    bad_body = "## Expanded datapoints\n\n### 1:00 — a\n**Quote:** x\n**Takeaway:** y\n"
    write_expanded_draft(
        row, bad_body, model="m", prompt_path=prompt, staging_root=staging, variant="A"
    )

    from expand_tune import draft_report_row

    rep = draft_report_row(row, "A", "r1")
    assert rep["draft_exists"]
    assert rep["n_bullets"] == 2
    assert rep["n_sections"] == 1
    assert any("fewer expanded" in e for e in rep["validation_errors"])
