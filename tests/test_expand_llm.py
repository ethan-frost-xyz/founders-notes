"""Tests for expand_llm (no network)."""

from pathlib import Path
from unittest.mock import patch

import paths
from expand_llm import (
    build_combined_prompt_for_clipboard,
    build_user_message,
    default_prompt_path,
    load_prompt_template,
    parse_expanded_body,
    promote_draft,
    validate_expanded_draft,
    write_expanded_draft,
)


def test_load_prompt_template_default():
    system, user = load_prompt_template(default_prompt_path())
    assert "<<<" not in system
    assert "{notes}" in user
    assert "{transcript}" in user


def test_build_user_message_substitution():
    _, user_tpl = load_prompt_template(default_prompt_path())
    u = build_user_message(user_tpl, notes="N", transcript="T")
    assert "N" in u and "T" in u


def test_build_combined_prompt_for_clipboard():
    p = build_combined_prompt_for_clipboard("SYS", "USER")
    assert "SYS" in p and "USER" in p


def test_parse_expanded_body_fenced():
    raw = """```markdown
## Expanded datapoints

### 1:00 — test
**Quote:** "hi"
**Takeaway:** ok
```
"""
    out = parse_expanded_body(raw)
    assert out.startswith("## Expanded datapoints")


def test_parse_expanded_body_unfenced():
    raw = "Preamble\n\n## Expanded datapoints\n\n### 1:00 — x\n**Quote:** a\n**Takeaway:** b\n"
    out = parse_expanded_body(raw)
    assert out.startswith("## Expanded datapoints")


def test_validate_expanded_draft_ok(tmp_path: Path):
    npath = tmp_path / "n.md"
    npath.write_text(
        "---\nid: x\n---\n\n## Raw datapoints\n\n- 1:00 — a\n- 2:00 — b\n",
        encoding="utf-8",
    )
    body = """## Expanded datapoints

### 1:00 — a
**Quote:** "q1"
**Takeaway:** t1

### 2:00 — b
**Quote:** "q2"
**Takeaway:** t2
"""
    errors, _warnings = validate_expanded_draft(npath, body)
    assert errors == []


def test_validate_expanded_draft_too_few_sections(tmp_path: Path):
    npath = tmp_path / "n.md"
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — a\n- 2:00 — b\n", encoding="utf-8"
    )
    body = "## Expanded datapoints\n\n### 1:00 — a\n**Quote:** x\n**Takeaway:** y\n"
    errors, _ = validate_expanded_draft(npath, body)
    assert any("fewer expanded" in e for e in errors)


def test_promote_draft_writes_expanded_and_removes_draft(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")

    row = {"id": "ep-0001", "slug": "1-test", "episode_number": 1, "title": "T"}
    npath = paths.notes_file_path("ep-0001", "1-test", 1)
    npath.parent.mkdir(parents=True)
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — hook\n", encoding="utf-8"
    )
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{notes}\n{transcript}\n")
    body = '## Expanded datapoints\n\n### 1:00 — hook\n**Quote:** "x"\n**Takeaway:** y\n'
    write_expanded_draft(row, body, model="test-model", prompt_path=prompt_file)
    draft = paths.expanded_draft_file_path("ep-0001", "1-test", 1)
    assert draft.exists()

    out_path, errors, _w = promote_draft(row, dry_run=False)
    assert errors == []
    assert out_path is not None
    exp = paths.expanded_file_path("ep-0001", "1-test", 1)
    assert exp == out_path
    assert exp.exists()
    assert not draft.exists()


@patch(
    "expand_datapoints_llm.call_openrouter",
    return_value='## Expanded datapoints\n\n### 1:00 — hook\n**Quote:** "x"\n**Takeaway:** y\n',
)
def test_expand_datapoints_llm_apply_writes_draft(mock_call, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")

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
    prompt_file.write_text("<<<SYSTEM>>>\nsystem here\n<<<USER>>>\n{notes}\n{transcript}\n")
    system, user_tpl = load_prompt_template(prompt_file)

    import expand_datapoints_llm as cli

    status = cli.run_expand_one(
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
    assert status == "wrote"
    mock_call.assert_called_once()
    assert paths.expanded_draft_file_path("ep-0001", "1-test", 1).exists()
