"""Unit tests for librarian suite history append."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEV = REPO / "dev"
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.response_report import HarnessReportPaths  # noqa: E402
from harness.scenario_runner import ScenarioResult, TurnResult  # noqa: E402
from harness.suite_history import append_librarian_run  # noqa: E402


def test_append_librarian_run_writes_history(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    history_seed = {
        "schema_version": "1.0",
        "suite": "librarian",
        "baseline_run_id": "baseline-run",
        "runs": [
            {
                "run_id": "baseline-run",
                "pass_count": 1,
                "scenario_count": 1,
                "total_wall_s": 2.0,
                "cap_hits": 0,
            }
        ],
    }
    (runs_dir / "librarian-suite-history.json").write_text(
        json.dumps(history_seed),
        encoding="utf-8",
    )
    report_json = runs_dir / "2026-06-11T12-00-00-report.json"
    report_json.write_text("{}", encoding="utf-8")
    results = [
        ScenarioResult(
            name="thematic_search",
            path=tmp_path / "dev/scenarios/librarian/thematic_search.yaml",
            passed=True,
            turns=[
                TurnResult(
                    1,
                    "send",
                    True,
                    "ok",
                    stop_reason="natural",
                    observability={"timing_enabled": True, "latency": {"wall_ms": 1000}},
                )
            ],
            elapsed_s=1.0,
        )
    ]
    scenario_paths = [tmp_path / "dev/scenarios/librarian/thematic_search.yaml"]
    scenario_paths[0].parent.mkdir(parents=True)

    history_path = append_librarian_run(
        report_paths=HarnessReportPaths(json=report_json, markdown=None),
        results=results,
        runs_dir=runs_dir,
        repo_root=tmp_path,
        scenario_paths=scenario_paths,
    )
    assert history_path is not None
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert history["schema_version"] == "1.0"
    assert len(history["runs"]) == 2
    latest = history["runs"][-1]
    assert latest["run_id"] == "2026-06-11T12-00-00"
    assert latest["delta_vs_baseline"]["pass_count_delta"] == 0
