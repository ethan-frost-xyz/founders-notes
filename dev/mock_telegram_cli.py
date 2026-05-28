#!/usr/bin/env python3
"""CLI entry for the mock Telegram harness (REPL and scenario runner)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_DEV_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _DEV_DIR.parent
if str(_DEV_DIR) not in sys.path:
    sys.path.insert(0, str(_DEV_DIR))

from harness.mock_session import DEFAULT_LOG_DIR  # noqa: E402
from harness.scenario_runner import ScenarioRunner, discover_scenarios  # noqa: E402
from harness.terminal import run_repl  # noqa: E402

SCENARIOS_ROOT = _DEV_DIR / "scenarios"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mock Telegram harness for Founders vault bot")
    parser.add_argument("--run-scenarios", action="store_true", help="Run all scenario YAML files")
    parser.add_argument("--suite", help="Run scenarios under a subfolder name (e.g. librarian)")
    parser.add_argument("--scenario", type=Path, help="Run a single scenario file")
    parser.add_argument("--debug", action="store_true", help="Show tool traces in REPL")
    parser.add_argument(
        "--stub-llm",
        action="store_true",
        help="Echo/stub LLM for all scenarios (no OPENROUTER_API_KEY)",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Preserve Janitor sandbox temp dirs under dev/logs/sandbox/",
    )
    return parser


async def _run_scenarios(args: argparse.Namespace) -> int:
    if args.scenario:
        paths = [args.scenario.resolve()]
    else:
        paths = discover_scenarios(SCENARIOS_ROOT, suite=args.suite)
    if not paths:
        print("No scenarios found.", file=sys.stderr)
        return 1

    runner = ScenarioRunner(
        log_dir=DEFAULT_LOG_DIR,
        stub_llm=args.stub_llm,
        keep_sandbox=args.keep_sandbox,
    )
    results = await runner.run_paths(paths)
    report = runner.write_report(results, DEFAULT_LOG_DIR / "runs")
    print(f"Report: {report}\n")
    for result in results:
        print(result.summary())
        print()
    return 0 if all(r.passed for r in results) else 1


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.run_scenarios or args.scenario:
        code = asyncio.run(_run_scenarios(args))
        raise SystemExit(code)

    llm_mode = "echo" if args.stub_llm else "live"
    run_repl(llm_mode=llm_mode, debug=args.debug, keep_sandbox=args.keep_sandbox)


if __name__ == "__main__":
    main()
