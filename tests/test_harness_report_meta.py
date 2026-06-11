"""Unit tests for harness report metadata / run_context."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEV = REPO / "dev"
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.report_meta import build_run_context  # noqa: E402


def _git_init_commit(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_build_run_context_single_scenario(tmp_path: Path, monkeypatch):
    _git_init_commit(tmp_path)
    scenario = tmp_path / "dev" / "scenarios" / "librarian" / "basic_qa.yaml"
    scenario.parent.mkdir(parents=True)
    scenario.write_text("name: test\n", encoding="utf-8")
    subprocess.run(["git", "add", scenario], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add scenario"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    monkeypatch.delenv("HARNESS_RUN_NOTE", raising=False)
    ctx = build_run_context(tmp_path, [scenario], run_note="librarian-live #1 basic_qa")
    assert ctx["run_note"] == "librarian-live #1 basic_qa"
    assert ctx["scenario_yaml"] == "basic_qa.yaml"
    assert ctx["scenario_path"] == "dev/scenarios/librarian/basic_qa.yaml"
    assert ctx["git_sha"] != "unknown"
    assert ctx["git_branch"] in {"main", "master"}
    assert ctx["git_dirty"] is False


def test_build_run_context_harness_run_note_env(tmp_path: Path, monkeypatch):
    _git_init_commit(tmp_path)
    scenario = tmp_path / "thematic_search.yaml"
    scenario.write_text("name: test\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_RUN_NOTE", "from-env")

    ctx = build_run_context(tmp_path, [scenario])
    assert ctx["run_note"] == "from-env"
