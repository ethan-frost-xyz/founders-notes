from pathlib import Path

from markdown_io import (
    count_notes_datapoints,
    escape_yaml_value,
    has_timestamp_datapoints,
    read_markdown_body,
    write_frontmatter_md,
)


def test_read_markdown_body_strips_frontmatter(tmp_path: Path):
    p = tmp_path / "note.md"
    p.write_text("---\nid: ep-0001\n---\n\n## Raw datapoints\n", encoding="utf-8")
    assert read_markdown_body(p) == "## Raw datapoints"


def test_has_timestamp_datapoints(tmp_path: Path):
    p = tmp_path / "note.md"
    p.write_text(
        "---\nid: ep-0001\n---\n\n## Raw datapoints\n\n- 12:34 — quote here\n",
        encoding="utf-8",
    )
    assert has_timestamp_datapoints(p) is True
    p.write_text("---\n---\n\n## Raw datapoints\n", encoding="utf-8")
    assert has_timestamp_datapoints(p) is False


def test_count_notes_datapoints_mixed_and_lost_timestamp():
    body = """## Raw datapoints

- 12:34 — good
- — lost timestamp
- 1:05:00 — also good
- —
"""
    counts = count_notes_datapoints(body)
    assert counts.timestamped == 2
    assert counts.missing_timestamp == 2


def test_count_notes_datapoints_lost_only(tmp_path: Path):
    body = "## Raw datapoints\n\n- — only this\n"
    counts = count_notes_datapoints(body)
    assert counts.timestamped == 0
    assert counts.missing_timestamp == 1
    p = tmp_path / "note.md"
    p.write_text(f"---\n---\n\n{body}", encoding="utf-8")
    assert has_timestamp_datapoints(p) is False


def test_write_frontmatter_roundtrip(tmp_path: Path):
    p = tmp_path / "out.md"
    write_frontmatter_md(p, frontmatter={"id": "ep-0001", "title": 'Say "hi"'}, body="body")
    text = p.read_text(encoding="utf-8")
    assert 'id: "ep-0001"' in text or "id: ep-0001" in text
    assert read_markdown_body(p) == "body"


def test_escape_yaml_value():
    assert escape_yaml_value('a"b') == "a'b"
