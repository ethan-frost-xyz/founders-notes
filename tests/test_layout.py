from layout import scan_layout_violations


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


def test_scan_layout_violations_bad_id():
    rows = [{"id": "ep-1", "episode_number": 1, "slug": "1-test", "transcript_status": "pending"}]
    errors = scan_layout_violations(rows)
    assert any("bad id format" in e for e in errors)
