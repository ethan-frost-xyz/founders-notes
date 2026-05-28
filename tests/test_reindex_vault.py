"""reindex_vault subprocess orchestration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from reindex_vault import main, reindex_vault

REPO = Path(__file__).resolve().parent.parent


def _make_vault(tmp_path: Path) -> Path:
    ingestion = tmp_path / "ingestion"
    (ingestion / "search").mkdir(parents=True)
    return tmp_path


def test_reindex_vault_runs_chunks_then_embeddings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("reindex_vault.subprocess.run", fake_run)

    code, msg = reindex_vault(vault, python="/usr/bin/python3")

    assert code == 0
    assert "embeddings" in msg
    assert len(calls) == 2
    assert calls[0] == ["/usr/bin/python3", "search/build_chunks.py"]
    assert calls[1] == ["/usr/bin/python3", "search/build_embeddings.py"]
    assert calls[0] is not calls[1]


def test_reindex_vault_embeddings_false_skips_second_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault = _make_vault(tmp_path)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("reindex_vault.subprocess.run", fake_run)

    code, msg = reindex_vault(vault, embeddings=False, python="/usr/bin/python3")

    assert code == 0
    assert "chunks" in msg.lower()
    assert len(calls) == 1
    assert calls[0][1] == "search/build_chunks.py"


def test_reindex_vault_chunks_failure_returns_tail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault = _make_vault(tmp_path)

    def fake_run(argv, **kwargs):
        return MagicMock(returncode=1, stdout="ok\n", stderr="chunk error\n")

    monkeypatch.setattr("reindex_vault.subprocess.run", fake_run)

    code, msg = reindex_vault(vault, python="/usr/bin/python3")

    assert code == 1
    assert "chunk error" in msg


def test_reindex_vault_sets_cwd_and_vault_root_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault = _make_vault(tmp_path)
    seen: list[tuple[str, dict[str, str]]] = []

    def fake_run(argv, **kwargs):
        seen.append((kwargs["cwd"], kwargs["env"]))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("reindex_vault.subprocess.run", fake_run)

    reindex_vault(vault, python="/usr/bin/python3")

    cwd, env = seen[0]
    assert cwd == str(vault / "ingestion")
    assert env["VAULT_ROOT"] == str(vault.resolve())


def test_reindex_vault_prefers_ingestion_venv_python(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    venv_py = vault / "ingestion" / ".venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\n", encoding="utf-8")

    from reindex_vault import _python

    assert _python(vault) == str(venv_py)


def test_reindex_vault_main_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() must import _bootstrap when only ingestion/lib is on sys.path (CLI)."""
    monkeypatch.setattr("reindex_vault.reindex_vault", lambda *a, **k: (0, "ok"))
    ingestion = str(REPO / "ingestion")
    lib = str(REPO / "ingestion" / "lib")
    saved_path = sys.path.copy()
    sys.modules.pop("_bootstrap", None)
    try:
        sys.path[:] = [lib] + [p for p in saved_path if p not in (ingestion, lib)]
        assert main() == 0
    finally:
        sys.path[:] = saved_path
