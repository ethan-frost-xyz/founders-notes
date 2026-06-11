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

from harness.env import (  # noqa: E402
    REPO_ROOT,
    format_preflight_report,
    live_harness_preflight,
    live_harness_ready,
    load_harness_env,
)
from harness.mock_session import DEFAULT_LOG_DIR  # noqa: E402
from harness.scenario_runner import (  # noqa: E402
    ScenarioRunner,
    aggregate_scenario_observability,
    aggregate_timing,
    discover_live_scenarios,
    discover_scenarios,
    format_timing_aggregate,
    paths_need_live_llm,
)
from harness.report_meta import build_run_context  # noqa: E402
from harness.suite_history import append_librarian_run  # noqa: E402
from harness.terminal import run_repl  # noqa: E402

SCENARIOS_ROOT = _DEV_DIR / "scenarios"


def _should_run_scenarios(args: argparse.Namespace) -> bool:
    return bool(args.run_scenarios or args.scenario or args.suite)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mock Telegram harness for Founders vault bot")
    parser.add_argument(
        "--run-scenarios",
        action="store_true",
        help="Run scenario YAML files (also implied by --scenario or --suite)",
    )
    parser.add_argument(
        "--suite",
        help="Run scenarios under a subfolder name (e.g. librarian); implies --run-scenarios",
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        help="Run a single scenario file; implies --run-scenarios",
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="When running scenarios, skip YAML files with llm: echo",
    )
    parser.add_argument("--debug", action="store_true", help="Show tool traces in REPL")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print tools_called per turn; include in JSON report",
    )
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
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Print live env + index checks and exit (use before --suite librarian --live-only)",
    )
    parser.add_argument(
        "--run-note",
        help="Tag this run in report JSON and librarian-suite-history (also HARNESS_RUN_NOTE env)",
    )
    return parser


async def _run_scenarios(args: argparse.Namespace) -> int:
    if args.scenario:
        paths = [args.scenario.resolve()]
    elif args.live_only:
        paths = discover_live_scenarios(SCENARIOS_ROOT, suite=args.suite)
    else:
        paths = discover_scenarios(SCENARIOS_ROOT, suite=args.suite)

    if not paths:
        print("No scenarios found.", file=sys.stderr)
        return 1

    if paths_need_live_llm(paths, stub_llm=args.stub_llm):
        ok, reason, meta = live_harness_preflight(REPO_ROOT)
        if not ok:
            print(f"Live harness preflight failed: {reason}", file=sys.stderr)
            print(
                "Use --stub-llm for keyless echo runs, or source "
                "~/.config/founders-telegram/env and rebuild the index",
                file=sys.stderr,
            )
            return 1
        if args.verbose:
            print(format_preflight_report(meta), file=sys.stderr)

    run_context = build_run_context(REPO_ROOT, paths, run_note=args.run_note)

    runner = ScenarioRunner(
        log_dir=DEFAULT_LOG_DIR,
        stub_llm=args.stub_llm,
        keep_sandbox=args.keep_sandbox,
        verbose=args.verbose,
    )
    results = await runner.run_paths(paths, verbose=args.verbose)
    runs_dir = DEFAULT_LOG_DIR / "runs"
    report_paths = runner.write_report(
        results,
        runs_dir,
        repo_root=REPO_ROOT,
        run_context=run_context,
    )
    history_path = append_librarian_run(
        report_paths=report_paths,
        results=results,
        runs_dir=runs_dir,
        repo_root=REPO_ROOT,
        scenario_paths=paths,
        run_context=run_context,
    )
    print(f"Report: {report_paths.json}")
    if report_paths.markdown is not None:
        print(f"Responses: {report_paths.markdown}")
    if history_path is not None:
        print(f"Suite history: {history_path}")
    if run_context.get("run_note"):
        print(f"Run note: {run_context['run_note']}")
    print()
    for result in results:
        print(result.summary(verbose=args.verbose))
        print()
    if args.verbose:
        agg = aggregate_timing(results)
        agg.update(aggregate_scenario_observability(results))
        print(format_timing_aggregate(agg))
        print()
    return 0 if all(r.passed for r in results) else 1


def main() -> None:
    loaded = load_harness_env(REPO_ROOT)
    parser = _build_parser()
    args = parser.parse_args()

    if args.preflight:
        ok, reason, meta = live_harness_preflight(REPO_ROOT)
        if ok:
            print(format_preflight_report(meta))
            raise SystemExit(0)
        print(f"Preflight failed: {reason}", file=sys.stderr)
        raise SystemExit(1)

    if _should_run_scenarios(args):
        if args.live_only and args.stub_llm:
            print("--live-only cannot be used with --stub-llm", file=sys.stderr)
            raise SystemExit(2)
        code = asyncio.run(_run_scenarios(args))
        raise SystemExit(code)

    if args.suite or args.live_only:
        print(
            "No scenarios run: pass --scenario PATH or use --suite with scenario mode.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if not args.stub_llm:
        ready, reason = live_harness_ready()
        if not ready:
            print(f"Live REPL: {reason}", file=sys.stderr)
            print("Tip: use --stub-llm for keyless debugging.", file=sys.stderr)
            raise SystemExit(1)

    if loaded and args.verbose:
        print(f"Loaded env: {', '.join(str(p) for p in loaded)}", file=sys.stderr)

    llm_mode = "echo" if args.stub_llm else "live"
    run_repl(llm_mode=llm_mode, debug=args.debug, keep_sandbox=args.keep_sandbox)


if __name__ == "__main__":
    main()
