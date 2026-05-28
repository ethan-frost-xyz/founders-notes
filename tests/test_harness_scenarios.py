"""Parametrized harness scenario tests (echo LLM, no network)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("telegram")
pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
DEV = REPO / "dev"
SCENARIOS = DEV / "scenarios"

if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from harness.scenario_runner import discover_scenarios  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_HARNESS_SCENARIOS") == "1",
    reason="SKIP_HARNESS_SCENARIOS=1",
)

_SCENARIO_PATHS = discover_scenarios(SCENARIOS)


@pytest.mark.parametrize("scenario_path", _SCENARIO_PATHS, ids=lambda p: p.stem)
def test_harness_scenario_echo(scenario_path: Path) -> None:
    import asyncio

    from harness.scenario_runner import ScenarioRunner

    runner = ScenarioRunner(stub_llm=True, log_dir=REPO / "dev" / "logs")
    result = asyncio.run(runner.run(scenario_path))
    assert result.passed, result.summary()
