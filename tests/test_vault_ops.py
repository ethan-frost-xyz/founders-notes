"""vault_ops git pull / reindex wrappers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vault_ops import run_git_pull, run_reindex, run_vault_push

REPO = Path(__file__).resolve().parent.parent


def _make_vault(tmp_path: Path) -> Path:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "episodes.jsonl").write_text(
        json.dumps({"id": "ep-0001", "episode_number": 1, "title": "First"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "ingestion" / "search").mkdir(parents=True)
    return tmp_path


def test_run_reindex_clears_catalog_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    episodes = vault / "catalog" / "episodes.jsonl"

    from catalog import load_jsonl

    assert load_jsonl(episodes)[0]["title"] == "First"

    episodes.write_text(
        json.dumps({"id": "ep-0001", "episode_number": 1, "title": "Updated"}) + "\n",
        encoding="utf-8",
    )
    assert load_jsonl(episodes)[0]["title"] == "First"

    monkeypatch.setenv("VAULT_ROOT", str(vault))
    with patch("reindex_vault.reindex_vault", return_value=(0, "ok")):
        code, msg = run_reindex(vault)

    assert code == 0
    assert msg == "ok"
    assert load_jsonl(episodes)[0]["title"] == "Updated"


def test_run_git_pull_clears_catalog_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    episodes = vault / "catalog" / "episodes.jsonl"

    from catalog import load_jsonl

    assert load_jsonl(episodes)[0]["title"] == "First"
    episodes.write_text(
        json.dumps({"id": "ep-0001", "episode_number": 1, "title": "Pulled"}) + "\n",
        encoding="utf-8",
    )
    assert load_jsonl(episodes)[0]["title"] == "First"

    monkeypatch.setenv("VAULT_ROOT", str(vault))
    with patch(
        "vault_ops.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="Already up to date.", stderr=""),
    ):
        code, msg = run_git_pull(vault)

    assert code == 0
    assert "Already up to date." in msg
    assert load_jsonl(episodes)[0]["title"] == "Pulled"


def test_run_vault_push_invokes_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    script = vault / "services" / "telegram" / "deploy" / "vault-push.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    script.chmod(0o755)

    calls: dict = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = kwargs.get("cwd")
        return MagicMock(returncode=0, stdout="vault-push: committed and pushed\n", stderr="")

    monkeypatch.setattr("vault_ops.subprocess.run", fake_run)
    code, msg = run_vault_push(
        vault,
        message="vault: test",
        episode_id="ep-0001",
        skip_verify=True,
    )

    assert code == 0
    assert "committed and pushed" in msg
    assert calls["cmd"][:3] == [str(script), "-m", "vault: test"]
    assert "--episode" in calls["cmd"]
    assert "ep-0001" in calls["cmd"]
    assert "--skip-verify" in calls["cmd"]
    assert calls["cwd"] == str(vault)
