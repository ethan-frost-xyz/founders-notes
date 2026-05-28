"""CLI ergonomics for dev/mock_telegram_cli.py."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEV = REPO / "dev"

if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.scenario_runner import discover_live_scenarios, discover_scenarios  # noqa: E402
from mock_telegram_cli import SCENARIOS_ROOT, _build_parser, _should_run_scenarios  # noqa: E402


def _parse(argv: list[str]) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def test_suite_implies_run_scenarios():
    assert _should_run_scenarios(_parse(["--suite", "librarian"]))
    assert _should_run_scenarios(_parse(["--scenario", "dev/scenarios/janitor/episode_parse.yaml"]))
    assert _should_run_scenarios(_parse(["--run-scenarios"]))
    assert not _should_run_scenarios(_parse([]))
    assert not _should_run_scenarios(_parse(["--debug"]))


def test_discover_live_scenarios_subset_of_all():
    all_paths = discover_scenarios(SCENARIOS_ROOT)
    live_paths = discover_live_scenarios(SCENARIOS_ROOT)
    assert live_paths
    assert set(live_paths) <= set(all_paths)
    assert all("librarian" in p.parts for p in live_paths)


def test_discover_live_scenarios_librarian_suite():
    live = discover_live_scenarios(SCENARIOS_ROOT, suite="librarian")
    stems = {p.stem for p in live}
    assert "episode_resolve" in stems
    assert "tool_coverage" in stems
