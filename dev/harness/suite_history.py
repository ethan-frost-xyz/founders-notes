"""Append librarian harness runs to a suite-scoped history file."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness.observability import aggregate_observability
from harness.report_meta import harness_git_sha
from harness.response_report import HarnessReportPaths

if TYPE_CHECKING:
    from harness.scenario_runner import ScenarioResult

HISTORY_SCHEMA_VERSION = "1.0"
HISTORY_FILENAME = "librarian-suite-history.json"


def is_librarian_run(paths: list[Path]) -> bool:
    if not paths:
        return False
    return all("librarian" in p.parts for p in paths)


def _cap_hits_from_results(results: list[ScenarioResult]) -> int:  # noqa: F821
    total = 0
    for result in results:
        for turn in result.turns:
            if turn.stop_reason == "cap":
                total += 1
    return total


def _load_history(path: Path) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "suite": "librarian",
        "baseline_run_id": None,
        "runs": [],
    }


def _delta_vs_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if baseline is None:
        return None
    wall_pct = None
    base_wall = float(baseline.get("total_wall_s") or 0)
    cur_wall = float(current.get("total_wall_s") or 0)
    if base_wall > 0:
        wall_pct = round((cur_wall - base_wall) / base_wall, 4)
    return {
        "pass_count_delta": int(current.get("pass_count") or 0)
        - int(baseline.get("pass_count") or 0),
        "wall_pct": wall_pct,
        "cap_hits_delta": int(current.get("cap_hits") or 0)
        - int(baseline.get("cap_hits") or 0),
    }


def append_librarian_run(
    *,
    report_paths: HarnessReportPaths,
    results: list[ScenarioResult],  # noqa: F821
    runs_dir: Path,
    repo_root: Path,
    scenario_paths: list[Path],
) -> Path | None:
    if not is_librarian_run(scenario_paths):
        return None

    history_path = runs_dir / HISTORY_FILENAME
    history = _load_history(history_path)
    run_id = report_paths.json.stem.replace("-report", "")
    pass_count = sum(1 for r in results if r.passed)
    total_wall_s = round(sum(r.elapsed_s for r in results), 1)
    cap_hits = _cap_hits_from_results(results)

    turn_obs = []
    for result in results:
        for turn in result.turns:
            if turn.observability:
                turn_obs.append({"observability": turn.observability})

    entry: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "report_path": str(report_paths.json.relative_to(repo_root)),
        "harness_version": harness_git_sha(repo_root),
        "passed": all(r.passed for r in results),
        "pass_count": pass_count,
        "scenario_count": len(results),
        "total_wall_s": total_wall_s,
        "cap_hits": cap_hits,
    }
    if report_paths.markdown is not None:
        entry["markdown_path"] = str(report_paths.markdown.relative_to(repo_root))

    baseline_run_id = history.get("baseline_run_id")
    baseline_entry = None
    if baseline_run_id:
        for run in history.get("runs") or []:
            if run.get("run_id") == baseline_run_id:
                baseline_entry = run
                break

    delta = _delta_vs_baseline(entry, baseline_entry)
    if delta is not None:
        entry["delta_vs_baseline"] = delta

    obs_agg = aggregate_observability(turn_obs)
    if obs_agg:
        entry["observability_aggregate"] = obs_agg

    runs: list[dict[str, Any]] = list(history.get("runs") or [])
    runs.append(entry)
    history["runs"] = runs
    history["schema_version"] = HISTORY_SCHEMA_VERSION
    history["suite"] = "librarian"
    if history.get("baseline_run_id") is None and runs:
        history["baseline_run_id"] = runs[0]["run_id"]

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history_path
