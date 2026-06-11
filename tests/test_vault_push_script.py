"""vault-push.sh integration tests (local git, no network)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "services" / "telegram" / "deploy" / "vault-push.sh"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _init_vault_with_remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    vault = tmp_path / "vault"
    vault.mkdir()
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    _git("init", "-b", "main", cwd=vault)
    _git("config", "user.email", "vault-push-test@example.com", cwd=vault)
    _git("config", "user.name", "vault-push test", cwd=vault)
    (vault / "README.md").write_text("init\n", encoding="utf-8")
    (vault / "catalog").mkdir()
    deploy = vault / "services" / "telegram" / "deploy"
    deploy.mkdir(parents=True)
    shutil.copy2(SCRIPT, deploy / "vault-push.sh")
    (deploy / "vault-push.sh").chmod(0o755)
    _git("add", "README.md", cwd=vault)
    _git("commit", "-m", "init", cwd=vault)
    _git("remote", "add", "origin", str(bare), cwd=vault)
    _git("push", "-u", "origin", "main", cwd=vault)
    return vault


def test_vault_push_dry_run_exits_zero(tmp_path: Path) -> None:
    vault = _init_vault_with_remote(tmp_path)
    env = {**os.environ, "VAULT_ROOT": str(vault)}
    proc = subprocess.run(
        [str(vault / "services" / "telegram" / "deploy" / "vault-push.sh"), "--dry-run", "--skip-verify"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "[dry-run]" in proc.stdout


def test_vault_push_commits_notes(tmp_path: Path) -> None:
    vault = _init_vault_with_remote(tmp_path)
    notes_dir = vault / "content" / "notes" / "ep-0001-test"
    notes_dir.mkdir(parents=True)
    (notes_dir / "ep-0001-test.notes.md").write_text("# notes\n", encoding="utf-8")

    env = {**os.environ, "VAULT_ROOT": str(vault)}
    proc = subprocess.run(
        [
            str(vault / "services" / "telegram" / "deploy" / "vault-push.sh"),
            "--skip-verify",
            "-m",
            "vault: test push",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "committed and pushed" in proc.stdout
    log = _git("log", "-1", "--oneline", cwd=vault)
    assert "vault: test push" in log.stdout


def test_vault_push_skips_when_sync_lock_held(tmp_path: Path) -> None:
    vault = _init_vault_with_remote(tmp_path)
    (vault / "catalog" / ".sync-in-progress").mkdir()
    env = {**os.environ, "VAULT_ROOT": str(vault)}
    proc = subprocess.run(
        [str(vault / "services" / "telegram" / "deploy" / "vault-push.sh"), "--skip-verify"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "sync-and-index in progress" in proc.stdout


def test_vault_push_no_op_when_tracked_reports_clean(tmp_path: Path) -> None:
    vault = _init_vault_with_remote(tmp_path)
    runs = vault / "dev/logs/runs"
    runs.mkdir(parents=True)
    report = runs / "2026-01-01T00-00-00-report.json"
    report.write_text("{}\n", encoding="utf-8")
    _git("add", str(report.relative_to(vault)), cwd=vault)
    _git("commit", "-m", "report", cwd=vault)

    env = {**os.environ, "VAULT_ROOT": str(vault)}
    proc = subprocess.run(
        [str(vault / "services" / "telegram" / "deploy" / "vault-push.sh"), "--skip-verify"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no whitelisted changes to commit" in proc.stdout
    assert "staged" not in proc.stdout


def test_vault_push_episode_resolve_dry_run_on_repo() -> None:
    env = {**os.environ, "VAULT_ROOT": str(REPO)}
    proc = subprocess.run(
        [str(SCRIPT), "--episode", "ep-0191", "--dry-run", "--skip-verify"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ep-0191-naval-ravikant-a-guide-to-wealth-and-happiness" in proc.stdout
