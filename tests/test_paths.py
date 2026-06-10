from pathlib import Path

from paths import (
    CATALOG_PATH,
    CHUNKS_PATH,
    EMBEDDINGS_MANIFEST_PATH,
    EMBEDDINGS_PATH,
    EPISODE_SUMMARIES_PATH,
    ROOT,
    TELEGRAM_SESSIONS_DIR,
    catalog_paths,
    content_filename,
    folder_name,
    notes_file_path,
    path_relative_to_root,
    transcript_path,
)


def test_path_relative_to_root(monkeypatch, tmp_path):
    import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    inside = tmp_path / "content" / "notes" / "ep.notes.md"
    inside.parent.mkdir(parents=True)
    assert path_relative_to_root(inside) == "content/notes/ep.notes.md"
    outside = Path("/tmp/outside.md")
    assert path_relative_to_root(outside) == str(outside)


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

    root = tmp_path / "runs" / "tune-001"
    p = staging_draft_file_path(root, "A", "ep-0001", "1-test", 1)
    assert p == root / "A" / "ep-0001-test" / "ep-0001-test.expanded.draft.md"


def test_catalog_paths_default_matches_module_constants():
    cp = catalog_paths()
    assert cp.root == ROOT
    assert cp.episodes == CATALOG_PATH
    assert cp.chunks == CHUNKS_PATH
    assert cp.embeddings == EMBEDDINGS_PATH
    assert cp.embeddings_manifest == EMBEDDINGS_MANIFEST_PATH
    assert cp.episode_summaries == EPISODE_SUMMARIES_PATH
    assert cp.telegram_sessions == TELEGRAM_SESSIONS_DIR


def test_catalog_paths_none_equals_default():
    assert catalog_paths(None) == catalog_paths()


def test_catalog_paths_sandbox_root(tmp_path):
    cp = catalog_paths(tmp_path)
    assert cp.root == tmp_path.resolve()
    assert cp.chunks == tmp_path / "catalog" / "chunks.jsonl"
    assert cp.embeddings == tmp_path / "catalog" / "embeddings.npy"
    assert cp.telegram_sessions == tmp_path / "catalog" / "telegram-sessions"
