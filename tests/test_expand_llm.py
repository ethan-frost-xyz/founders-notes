"""Tests for expand_llm (no network)."""

from pathlib import Path
from unittest.mock import patch

import pytest

import paths
from expand_llm import (
    CHARS_PER_TOKEN,
    OPENROUTER_MAX_ATTEMPTS,
    OpenRouterCompletion,
    TerminalExpandProgressReporter,
    build_combined_prompt_for_clipboard,
    build_user_message,
    call_openrouter,
    call_openrouter_streaming,
    count_datapoint_headings_in_partial,
    default_prompt_path,
    estimate_expand_for_row,
    execute_openrouter_with_retry,
    is_retriable_openrouter_error,
    load_prompt_template,
    parse_expanded_body,
    print_expand_batch_summary,
    promote_draft,
    usage_from_response,
    validate_expanded_draft,
    write_expanded_draft,
)

SAMPLE_EXPANDED_BODY = """## Expanded datapoints

### 1:00 — a

Context: Story setup at this beat.

Quote: **core phrase** surrounding context words. (1:00)

Key takeaway: Bigger picture lesson one.

### 2:00 — b

Context: Second beat context.

Quote: **key line** from transcript. (2:00)

Key takeaway: Bigger picture lesson two.
"""


def test_estimate_expand_for_row_counts_input_once(monkeypatch, tmp_path: Path):
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
    txpath.write_text("---\n---\n\nTRANSCRIPT\n", encoding="utf-8")

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text(
        "<<<SYSTEM>>>\nSYS\n<<<USER>>>\n{notes}\n{transcript}\n", encoding="utf-8"
    )
    from markdown_io import read_markdown_body

    system, user_tpl = load_prompt_template(prompt_file)
    notes_body = read_markdown_body(paths.notes_file_path("ep-0001", "1-test", 1))
    tx_body = read_markdown_body(txpath)
    user_msg = build_user_message(user_tpl, notes=notes_body, transcript=tx_body)
    est = estimate_expand_for_row(row, prompt_path=prompt_file)
    assert est.n_bullets == 1
    assert est.input_chars == len(system) + len(user_msg)
    legacy_double_count = est.notes_chars + est.transcript_chars + len(system) + len(user_msg)
    assert est.input_chars < legacy_double_count
    assert est.approx_input_tokens == (est.input_chars + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def test_load_prompt_template_default():
    system, user = load_prompt_template(default_prompt_path())
    assert "<<<" not in system
    assert "## Expanded datapoints" in system
    assert "first line" in system.lower()
    assert "{notes}" in user
    assert "{transcript}" in user
    assert "Context:" in user
    assert "Key takeaway:" in user
    assert "do not output" in user.lower()


def test_build_user_message_substitution():
    _, user_tpl = load_prompt_template(default_prompt_path())
    u = build_user_message(user_tpl, notes="N", transcript="T")
    assert "N" in u and "T" in u


def test_build_combined_prompt_for_clipboard():
    p = build_combined_prompt_for_clipboard("SYS", "USER")
    assert "SYS" in p and "USER" in p


def test_parse_expanded_body_fenced():
    raw = f"""```markdown
{SAMPLE_EXPANDED_BODY}
```
"""
    out = parse_expanded_body(raw)
    assert out.startswith("## Expanded datapoints")


def test_parse_expanded_body_unfenced():
    raw = f"Preamble\n\n{SAMPLE_EXPANDED_BODY}\n"
    out = parse_expanded_body(raw)
    assert out.startswith("## Expanded datapoints")


def test_validate_expanded_draft_ok(tmp_path: Path):
    npath = tmp_path / "n.md"
    npath.write_text(
        "---\nid: x\n---\n\n## Raw datapoints\n\n- 1:00 — a\n- 2:00 — b\n",
        encoding="utf-8",
    )
    errors, warnings = validate_expanded_draft(npath, SAMPLE_EXPANDED_BODY)
    assert errors == []
    assert warnings == []


def test_validate_expanded_draft_legacy_takeaway_ok(tmp_path: Path):
    npath = tmp_path / "n.md"
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — a\n", encoding="utf-8"
    )
    body = """## Expanded datapoints

### 1:00 — a

Context: c

Quote: "q" (1:00)

Takeaway: t
"""
    errors, _ = validate_expanded_draft(npath, body)
    assert errors == []


def test_validate_expanded_draft_too_few_sections(tmp_path: Path):
    npath = tmp_path / "n.md"
    npath.write_text(
        "---\n---\n\n## Raw datapoints\n\n- 1:00 — a\n- 2:00 — b\n", encoding="utf-8"
    )
    body = """## Expanded datapoints

### 1:00 — a

Context: c

Quote: "q" (1:00)

Key takeaway: t
"""
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
    body = """## Expanded datapoints

### 1:00 — hook

Context: c

Quote: **x** (1:00)

Key takeaway: y
"""
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


def test_usage_from_response_extracts_tokens_and_cost():
    usage = type("Usage", (), {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost": 0.05})()
    response = type("Resp", (), {"usage": usage})()
    parsed = usage_from_response(response)
    assert parsed["prompt_tokens"] == 100
    assert parsed["completion_tokens"] == 50
    assert parsed["cost_usd"] == 0.05


def test_print_expand_batch_summary(capsys):
    records = [
        {"status": "ok", "prompt_tokens": 1000, "completion_tokens": 200, "cost_usd": 0.01},
        {"status": "skipped"},
        {"status": "error"},
    ]
    print_expand_batch_summary(records, title="--- test summary ---")
    out = capsys.readouterr().out
    assert "ok: 1" in out
    assert "skipped: 1" in out
    assert "error: 1" in out
    assert "1,000 in" in out


def test_count_datapoint_headings_in_partial():
    partial = "## Expanded datapoints\n\n### 1:00 — a\n\nContext:\n"
    assert count_datapoint_headings_in_partial(partial) == 1
    full = partial + "\n### 2:00 — b\n"
    assert count_datapoint_headings_in_partial(full) == 2


def test_terminal_expand_progress_reporter(capsys):
    reporter = TerminalExpandProgressReporter(episode_id="ep-0001", total_sections=2)
    reporter.waiting(input_chars=120_000)
    reporter.first_token(ttft_ms=1500)
    reporter.section(index=1, total=2)
    out = capsys.readouterr().out
    assert "waiting for API" in out
    assert "first output" in out
    assert "datapoint 1/2" in out


def test_is_retriable_openrouter_error_empty_response():
    assert is_retriable_openrouter_error(ValueError("empty model response"))


def test_is_retriable_openrouter_error_parse_failure_not_retriable():
    assert not is_retriable_openrouter_error(
        ValueError("Model output missing '## Expanded datapoints'")
    )


@patch("expand_llm.time.sleep")
def test_execute_openrouter_with_retry_succeeds_on_third_attempt(mock_sleep):
    attempts = {"n": 0}

    def flaky() -> OpenRouterCompletion:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("empty model response")
        return OpenRouterCompletion(
            content="ok",
            response_id=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=None,
            duration_ms=0,
        )

    out = execute_openrouter_with_retry(flaky, max_attempts=OPENROUTER_MAX_ATTEMPTS)
    assert out.content == "ok"
    assert attempts["n"] == 3
    assert mock_sleep.call_count == 2


@patch("expand_llm.time.sleep")
def test_execute_openrouter_with_retry_raises_after_max_attempts(mock_sleep):
    def always_fail() -> OpenRouterCompletion:
        raise ValueError("empty model response")

    with pytest.raises(ValueError, match="empty model response"):
        execute_openrouter_with_retry(always_fail, max_attempts=OPENROUTER_MAX_ATTEMPTS)
    assert mock_sleep.call_count == OPENROUTER_MAX_ATTEMPTS - 1


@patch("expand_llm.time.sleep")
@patch("openai.OpenAI")
def test_call_openrouter_retries_transient_failure(mock_openai_cls, mock_sleep):
    usage = type(
        "Usage",
        (),
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "cost": None},
    )()
    ok_response = type(
        "Resp",
        (),
        {
            "id": "r1",
            "choices": [type("C", (), {"message": type("M", (), {"content": "## Expanded datapoints\n"})()})()],
            "usage": usage,
        },
    )()
    mock_openai_cls.return_value.chat.completions.create.side_effect = [
        ValueError("empty model response"),
        ok_response,
    ]

    completion = call_openrouter(
        system="s",
        user="u",
        model="m",
        api_key="k",
        episode_id="ep-0001",
    )
    assert completion.content.startswith("## Expanded datapoints")
    assert mock_openai_cls.return_value.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once()


@patch("openai.OpenAI")
def test_call_openrouter_streaming_assembles_content(mock_openai_cls):
    usage = type(
        "Usage",
        (),
        {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30, "cost": 0.01},
    )()

    def make_chunk(content: str | None, *, with_usage: bool = False):
        delta = type("Delta", (), {"content": content})()
        choice = type("Choice", (), {"delta": delta})()
        return type(
            "Chunk",
            (),
            {
                "id": "chunk-1",
                "choices": [choice],
                "usage": usage if with_usage else None,
            },
        )()

    chunks = [
        make_chunk("## Expanded datapoints\n\n"),
        make_chunk("### 1:00 — a\n\n"),
        make_chunk("Context: x\n"),
        make_chunk(None, with_usage=True),
    ]
    mock_openai_cls.return_value.chat.completions.create.return_value = iter(chunks)

    completion = call_openrouter_streaming(
        system="sys",
        user="user",
        model="test/model",
        api_key="key",
        total_sections=1,
    )
    assert "## Expanded datapoints" in completion.content
    assert "### 1:00 — a" in completion.content
    assert completion.prompt_tokens == 10
    assert completion.completion_tokens == 20
    mock_openai_cls.return_value.chat.completions.create.assert_called_once()
    _, kwargs = mock_openai_cls.return_value.chat.completions.create.call_args
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}


@patch("expand_datapoints_llm.call_openrouter_streaming")
def test_expand_datapoints_llm_apply_writes_draft(mock_call, monkeypatch, tmp_path: Path):
    mock_call.return_value = OpenRouterCompletion(
        content="""## Expanded datapoints

### 1:00 — hook

Context: c

Quote: **x** (1:00)

Key takeaway: y
""",
        response_id="r1",
        prompt_tokens=500,
        completion_tokens=100,
        total_tokens=600,
        cost_usd=0.002,
        duration_ms=1200,
    )
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(paths, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(
        "expand_llm.expand_run_log_path",
        lambda: tmp_path / "catalog" / "expand-run.jsonl",
    )

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

    status, _log_rec = cli.run_expand_one(
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
    log_path = tmp_path / "catalog" / "expand-run.jsonl"
    assert log_path.exists()
    log_line = log_path.read_text(encoding="utf-8").strip()
    assert '"status": "ok"' in log_line
    assert '"prompt_tokens": 500' in log_line
