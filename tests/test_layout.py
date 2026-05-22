import layout
from layout import EXPANDED_DRAFT_RE, scan_layout_violations


def test_expanded_draft_filename_pattern():
    m = EXPANDED_DRAFT_RE.match("ep-0001-test.expanded.draft.md")
    assert m is not None
    assert m.group("folder") == "ep-0001-test"


def test_scan_layout_violations_valid_row():
    rows = [
        {
            "id": "ep-0001",
            "episode_number": 1,
            "slug": "1-test-episode",
            "transcript_status": "complete",
            "transcript_path": "content/transcripts/ep-0001-test-episode/ep-0001-test-episode.transcript.md",
        }
    ]
    # May report filesystem violations if dirs missing; id checks should pass
    errors = [e for e in scan_layout_violations(rows) if "bad id" in e or "id mismatch" in e]
    assert errors == []


def test_scan_layout_allows_expanded_draft(monkeypatch, tmp_path):
    monkeypatch.setattr(layout, "ROOT", tmp_path)
    monkeypatch.setattr(layout, "NOTES_DIR", tmp_path / "content" / "notes")
    monkeypatch.setattr(layout, "TRANSCRIPTS_DIR", tmp_path / "content" / "transcripts")
    monkeypatch.setattr(layout, "POSTS_DIR", tmp_path / "content" / "posts")

    nd = tmp_path / "content" / "notes" / "ep-0001-x"
    nd.mkdir(parents=True)
    (nd / "ep-0001-x.expanded.draft.md").write_text("---\n---\n\n## Expanded datapoints\n")
    td = tmp_path / "content" / "transcripts" / "ep-0001-x"
    td.mkdir(parents=True)
    (td / "ep-0001-x.transcript.md").write_text("---\n---\n\nx")
    rows = [
        {
            "id": "ep-0001",
            "episode_number": 1,
            "slug": "1-x",
            "transcript_status": "complete",
            "transcript_path": "content/transcripts/ep-0001-x/ep-0001-x.transcript.md",
        }
    ]
    errs = scan_layout_violations(rows)
    assert not any("unexpected file" in e for e in errs)


def test_scan_layout_violations_bad_id():
    rows = [{"id": "ep-1", "episode_number": 1, "slug": "1-test", "transcript_status": "pending"}]
    errors = scan_layout_violations(rows)
    assert any("bad id format" in e for e in errors)
