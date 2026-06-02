"""Tests for incremental episode summary index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import paths
from build_summaries import build_episode_summaries, content_hash, load_existing_summaries


def test_content_hash_changes_when_post_changes():
    h1 = content_hash("expanded body", "post a")
    h2 = content_hash("expanded body", "post b")
    assert h1 != h2


def test_build_summaries_skips_unchanged_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import build_summaries as mod

    ep_id = "ep-0998"
    summaries_path = tmp_path / "episode-summaries.jsonl"
    chash = content_hash("expanded", "")
    summaries_path.write_text(
        json.dumps(
            {
                "episode_id": ep_id,
                "title": "T",
                "summary_text": "Existing summary",
                "content_hash": chash,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    from catalog import clear_jsonl_cache

    clear_jsonl_cache()
    row = {"id": ep_id, "slug": "998-test", "episode_number": 998, "title": "T"}

    monkeypatch.setattr(mod, "load_catalog", lambda: [row])
    exp_path = tmp_path / "x.expanded.md"
    exp_path.write_text("expanded", encoding="utf-8")
    monkeypatch.setattr(mod, "episode_is_studied", lambda _p: True)
    monkeypatch.setattr("build_chunks.episode_is_studied", lambda _p: True)
    monkeypatch.setattr(mod, "expanded_file_path", lambda *_a, **_k: exp_path)
    monkeypatch.setattr(mod, "post_file_path", lambda *_a, **_k: tmp_path / "x.post.md")
    monkeypatch.setattr(mod, "_read_optional", lambda p: "expanded" if p == exp_path else "")
    monkeypatch.setattr(paths, "EPISODE_SUMMARIES_PATH", summaries_path)
    monkeypatch.setattr(
        mod,
        "generate_summary",
        lambda **_k: (_ for _ in ()).throw(AssertionError("should not call LLM")),
    )

    summary = build_episode_summaries(apply=True)
    assert summary["to_generate"] == 0
    assert summary["reused"] == 1
    assert "Existing summary" in summaries_path.read_text(encoding="utf-8")


def test_build_summaries_calls_llm_when_hash_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import build_summaries as mod

    ep_id = "ep-0997"
    summaries_path = tmp_path / "episode-summaries.jsonl"
    summaries_path.write_text(
        json.dumps(
            {
                "episode_id": ep_id,
                "title": "T",
                "summary_text": "Old",
                "content_hash": "deadbeef",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    from catalog import clear_jsonl_cache

    clear_jsonl_cache()
    row = {"id": ep_id, "slug": "997-test", "episode_number": 997, "title": "T"}

    exp_path = tmp_path / "x.expanded.md"
    exp_path.write_text("expanded", encoding="utf-8")
    monkeypatch.setattr(mod, "load_catalog", lambda: [row])
    monkeypatch.setattr(mod, "episode_is_studied", lambda _p: True)
    monkeypatch.setattr("build_chunks.episode_is_studied", lambda _p: True)
    monkeypatch.setattr(mod, "expanded_file_path", lambda *_a, **_k: exp_path)
    monkeypatch.setattr(mod, "post_file_path", lambda *_a, **_k: tmp_path / "x.post.md")
    monkeypatch.setattr(mod, "_read_optional", lambda p: "new body" if p == exp_path else "")
    monkeypatch.setattr(paths, "EPISODE_SUMMARIES_PATH", summaries_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "test/model")

    called: list[str] = []

    def fake_gen(**_k):
        called.append("yes")
        return "Fresh summary text"

    monkeypatch.setattr(mod, "generate_summary", fake_gen)

    summary = build_episode_summaries(apply=True)
    assert summary["to_generate"] == 1
    assert called
    clear_jsonl_cache()
    stored = load_existing_summaries(summaries_path)[ep_id]
    assert stored["summary_text"] == "Fresh summary text"
