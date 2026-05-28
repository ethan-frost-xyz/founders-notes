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

from harness.env import live_harness_ready, load_harness_env  # noqa: E402
from harness.scenario_runner import discover_live_scenarios, discover_scenarios  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_HARNESS_SCENARIOS") == "1",
    reason="SKIP_HARNESS_SCENARIOS=1",
)

_SCENARIO_PATHS = discover_scenarios(SCENARIOS)
_LIVE_SCENARIO_PATHS = discover_live_scenarios(SCENARIOS)


@pytest.mark.parametrize("scenario_path", _SCENARIO_PATHS, ids=lambda p: p.stem)
def test_harness_scenario_echo(scenario_path: Path) -> None:
    import asyncio

    from harness.scenario_runner import ScenarioRunner

    runner = ScenarioRunner(stub_llm=True, log_dir=REPO / "dev" / "logs")
    result = asyncio.run(runner.run(scenario_path))
    assert result.passed, result.summary()


@pytest.mark.parametrize("scenario_path", _LIVE_SCENARIO_PATHS, ids=lambda p: p.stem)
def test_harness_scenario_live(scenario_path: Path) -> None:
    """Opt-in OpenRouter smoke: RUN_LIVE_HARNESS=1 pytest tests/test_harness_scenarios.py -k live -q"""
    if os.environ.get("RUN_LIVE_HARNESS") != "1":
        pytest.skip("Set RUN_LIVE_HARNESS=1 for live harness (OpenRouter)")

    import asyncio

    from harness.scenario_runner import ScenarioRunner

    load_harness_env(REPO)
    ready, reason = live_harness_ready()
    if not ready:
        pytest.skip(reason)

    runner = ScenarioRunner(stub_llm=False, log_dir=REPO / "dev" / "logs")
    result = asyncio.run(runner.run(scenario_path))
    assert result.passed, result.summary(verbose=True)
