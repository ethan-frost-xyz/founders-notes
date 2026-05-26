"""Tests for expand apply-run logging."""

from pathlib import Path
from unittest.mock import patch

import paths
from expand_llm import OpenRouterCompletion, filter_expand_run_log, load_expand_run_log


@patch("expand_datapoints_llm.call_openrouter")
def test_run_expand_one_skipped_logs(mock_call, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(
        "expand_llm.expand_run_log_path",
        lambda: tmp_path / "catalog" / "expand-run.jsonl",
    )

    import expand_datapoints_llm as cli

    row = {"id": "ep-0001", "slug": "1-test", "episode_number": 1, "title": "T"}
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n", encoding="utf-8"
    )
    txdir = paths.transcript_dir("ep-0001", "1-test", 1)
    txdir.mkdir(parents=True)
    txpath = txdir / paths.transcript_filename("ep-0001", "1-test", 1)
    txpath.write_text("---\n---\n\nbody\n", encoding="utf-8")

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("<<<SYSTEM>>>\ns\n<<<USER>>>\n{notes}\n{transcript}\n", encoding="utf-8")
    from expand_llm import load_prompt_template

    system, user_tpl = load_prompt_template(prompt_file)

    draft = paths.expanded_draft_file_path("ep-0001", "1-test", 1)
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("---\n---\n\n## Expanded datapoints\n", encoding="utf-8")

    status, log_rec = cli.run_expand_one(
        row,
        system=system,
        user_template=user_tpl,
        prompt_path=prompt_file,
        model="m",
        api_key="k",
        base_url=None,
        dry_run=False,
        force=False,
    )
    assert status == "skipped"
    mock_call.assert_not_called()
    assert log_rec is not None
    assert log_rec["status"] == "skipped"


def test_filter_expand_run_log_by_run_id():
    records = [
        {"run_id": "tune-001", "variant": "A", "status": "ok"},
        {"run_id": "tune-002", "variant": "A", "status": "ok"},
        {"run_id": "tune-001", "variant": "B", "status": "error"},
    ]
    filtered = filter_expand_run_log(records, run_id="tune-001", variant="A")
    assert len(filtered) == 1
    assert filtered[0]["status"] == "ok"


@patch("expand_datapoints_llm.parse_expanded_body")
@patch("expand_datapoints_llm.call_openrouter_streaming")
def test_run_expand_one_parse_error_logs_usage(
    mock_call, mock_parse, monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(
        "expand_llm.expand_run_log_path",
        lambda: tmp_path / "catalog" / "expand-run.jsonl",
    )

    import expand_datapoints_llm as cli

    row = {"id": "ep-0001", "slug": "1-test", "episode_number": 1, "title": "T"}
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n", encoding="utf-8"
    )
    txdir = paths.transcript_dir("ep-0001", "1-test", 1)
    txdir.mkdir(parents=True)
    txpath = txdir / paths.transcript_filename("ep-0001", "1-test", 1)
    txpath.write_text("---\n---\n\nbody\n", encoding="utf-8")

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("<<<SYSTEM>>>\ns\n<<<USER>>>\n{notes}\n{transcript}\n", encoding="utf-8")
    from expand_llm import load_prompt_template

    system, user_tpl = load_prompt_template(prompt_file)

    mock_call.return_value = OpenRouterCompletion(
        content="### 1:00 — hook\n",
        response_id="resp-parse-fail",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.001,
        duration_ms=1200,
    )
    mock_parse.side_effect = ValueError("Model output missing '## Expanded datapoints'")

    status, log_rec = cli.run_expand_one(
        row,
        system=system,
        user_template=user_tpl,
        prompt_path=prompt_file,
        model="m",
        api_key="k",
        base_url=None,
        dry_run=False,
        force=True,
    )
    assert status == "error"
    assert log_rec is not None
    assert log_rec["status"] == "error"
    assert log_rec["prompt_tokens"] == 100
    assert log_rec["completion_tokens"] == 50
    assert log_rec["total_tokens"] == 150
    assert log_rec["cost_usd"] == 0.001
    assert log_rec["duration_ms"] == 1200
    assert log_rec["response_id"] == "resp-parse-fail"


def test_load_expand_run_log_empty(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "expand_llm.expand_run_log_path",
        lambda: tmp_path / "missing.jsonl",
    )
    assert load_expand_run_log() == []
