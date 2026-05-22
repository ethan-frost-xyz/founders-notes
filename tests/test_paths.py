from paths import content_filename, folder_name, notes_file_path, transcript_path


def test_folder_name_strips_episode_prefix():
    assert (
        folder_name("ep-0418", "418-phil-knight-founder-of-nike", 418)
        == "ep-0418-phil-knight-founder-of-nike"
    )


def test_content_filename():
    assert content_filename("ep-0001-elon", "notes") == "ep-0001-elon.notes.md"


def test_transcript_path_relative():
    rel = transcript_path("ep-0200", "200-james-dyson-against-the-odds", 200)
    assert rel.startswith("content/transcripts/ep-0200-")
    assert rel.endswith(".transcript.md")


def test_notes_file_path_under_notes_dir():
    p = notes_file_path("ep-0001", "1-test", 1)
    assert "content/notes" in str(p)
    assert p.name == "ep-0001-test.notes.md"


def test_expanded_draft_file_path():
    from paths import expanded_draft_file_path

    p = expanded_draft_file_path("ep-0001", "1-test", 1)
    assert p.name == "ep-0001-test.expanded.draft.md"


def test_staging_draft_file_path(tmp_path):
    from paths import staging_draft_file_path

    root = tmp_path / "run"
    p = staging_draft_file_path(root, "B", "ep-0001", "1-test", 1)
    assert p.parent.name == "ep-0001-test"
    assert "B" in p.parts
    assert p.name.endswith(".expanded.draft.md")
