"""Harness environment preflight helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

import sys

DEV = REPO / "dev"
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.env import live_harness_preflight  # noqa: E402


def test_live_harness_preflight_passes_on_fixture_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Minimal vault clone: embeddings.npy is gitignored on the real repo."""
    import numpy as np

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "test/model")

    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "chunks.jsonl").write_text(
        "\n".join('{"chunk_id":"fixture-%03d"}' % i for i in range(101)) + "\n",
        encoding="utf-8",
    )
    np.save(catalog / "embeddings.npy", np.zeros((1, 4), dtype=np.float32))

    ok, reason, meta = live_harness_preflight(tmp_path)
    assert ok, reason
    assert int(meta["chunk_count"]) > 100  # type: ignore[arg-type]
    assert meta["embeddings_present"] is True


def test_live_harness_preflight_fails_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_MODEL", "test/model")
    ok, reason, _meta = live_harness_preflight(REPO)
    assert not ok
    assert "OPENROUTER_API_KEY" in reason
