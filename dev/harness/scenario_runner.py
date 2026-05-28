"""YAML scenario loader and assertion engine for the mock Telegram harness."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from harness.janitor_sandbox import JanitorSandbox
from harness.mock_session import MockBotSession, Reply

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


@dataclass
class TurnResult:
    index: int
    action: str
    passed: bool
    message: str
    replies: list[Reply] = field(default_factory=list)
    elapsed_s: float = 0.0
    tools_called: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    name: str
    path: Path
    passed: bool
    turns: list[TurnResult] = field(default_factory=list)
    elapsed_s: float = 0.0
    llm_mode: str = "live"

    def summary(self, *, verbose: bool = False) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"{status}  {self.name}  ({self.elapsed_s:.1f}s, {self.llm_mode})"]
        for turn in self.turns:
            mark = "ok" if turn.passed else "FAIL"
            line = f"  [{mark}] turn {turn.index}: {turn.action} — {turn.message}"
            if verbose and turn.tools_called:
                line += f" (tools: {', '.join(turn.tools_called)})"
            lines.append(line)
        return "\n".join(lines)


def load_scenario(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
    else:
        raise RuntimeError("PyYAML is required for scenario files: pip install pyyaml")
    if not isinstance(data, dict):
        raise ValueError(f"Scenario must be a mapping: {path}")
    return data


def _all_reply_text(replies: list[Reply]) -> str:
    return "\n".join(r.text for r in replies)


def _check_expectations(
    expect: dict[str, Any],
    *,
    replies: list[Reply],
    tool_traces: list[dict[str, Any]],
    janitor_phase: str | None,
    sandbox_inspect: dict[str, Any] | None,
    llm_mode: str,
) -> tuple[bool, str]:
    combined = _all_reply_text(replies)

    if "contains" in expect:
        needle = str(expect["contains"])
        if needle not in combined:
            return False, f"expected reply to contain {needle!r}"

    if "not_contains" in expect:
        needle = str(expect["not_contains"])
        if needle in combined:
            return False, f"expected reply not to contain {needle!r}"

    min_len = expect.get("response_min_length")
    if min_len is not None and len(combined) < int(min_len):
        return False, f"response length {len(combined)} < {min_len}"

    live_only = expect.get("expect_live") or {}
    if llm_mode == "live":
        merged = {**expect, **live_only}
    else:
        merged = {k: v for k, v in expect.items() if k != "expect_live"}
        merged = {**merged, **{k: v for k, v in live_only.items() if k in ("phase", "sandbox_file_written")}}

    tool_called = merged.get("tool_called")
    if tool_called and llm_mode == "live":
        names = [t.get("tool") for t in tool_traces]
        if tool_called not in names:
            return False, f"expected tool {tool_called!r}, got {names!r}"

    response_contains = merged.get("response_contains")
    if response_contains and llm_mode == "live":
        if str(response_contains) not in combined:
            return False, f"expected response to contain {response_contains!r}"

    response_any = merged.get("response_contains_any")
    if response_any and llm_mode == "live":
        needles = [str(x) for x in response_any]
        if not any(n in combined for n in needles):
            return False, f"expected response to contain one of {needles!r}"

    load_episode_id = merged.get("load_episode_id")
    if load_episode_id and llm_mode == "live":
        expected = str(load_episode_id)
        seen: list[str] = []
        matched = False
        for t in tool_traces:
            if t.get("tool") != "load_episode":
                continue
            arg = str((t.get("arguments") or {}).get("episode_id", ""))
            seen.append(arg)
            if arg == expected:
                matched = True
                break
            try:
                from vault import resolve_episode_ref

                if resolve_episode_ref(arg) == expected:
                    matched = True
                    break
            except Exception:
                pass
        if not matched:
            return False, (
                f"expected load_episode resolving to {expected!r}, "
                f"episode_id args were {seen!r}"
            )

    phase = merged.get("phase")
    if phase is not None:
        if janitor_phase != str(phase):
            return False, f"expected janitor phase {phase!r}, got {janitor_phase!r}"

    sandbox_file = merged.get("sandbox_file_written")
    if sandbox_file and sandbox_inspect is not None:
        files = sandbox_inspect.get("files") or []
        needle = str(sandbox_file)
        if not any(needle in f for f in files):
            return False, f"expected sandbox file matching {needle!r}, got {files!r}"

    return True, "ok"


class ScenarioRunner:
    def __init__(
        self,
        *,
        log_dir: Path | None = None,
        stub_llm: bool = False,
        keep_sandbox: bool = False,
        verbose: bool = False,
    ) -> None:
        self.log_dir = log_dir
        self.stub_llm = stub_llm
        self.keep_sandbox = keep_sandbox
        self.verbose = verbose

    async def run(self, scenario_path: Path, session: MockBotSession | None = None) -> ScenarioResult:
        scenario = load_scenario(scenario_path)
        name = str(scenario.get("name") or scenario_path.stem)
        file_llm = str(scenario.get("llm") or "live").lower()
        llm_mode: Literal["live", "echo"] = "echo" if self.stub_llm or file_llm == "echo" else "live"

        janitor_episode = scenario.get("janitor_episode")
        sandbox_ctx: JanitorSandbox | None = None
        own_session = session is None

        if janitor_episode:
            sandbox_ctx = JanitorSandbox(episode_id=str(janitor_episode), keep=self.keep_sandbox)
            sandbox_ctx.__enter__()

        if own_session:
            session = MockBotSession(
                llm_mode=llm_mode,
                log_dir=self.log_dir,
                janitor_sandbox=sandbox_ctx,
            )
            await session.start()

        assert session is not None
        turn_results: list[TurnResult] = []
        t0 = time.perf_counter()
        all_passed = True

        try:
            for idx, turn in enumerate(scenario.get("turns") or [], start=1):
                turn_t0 = time.perf_counter()
                action = ""
                replies: list[Reply] = []

                if "send" in turn:
                    action = f"send {turn['send']!r}"
                    session.tool_traces.clear()
                    replies = await session.send(str(turn["send"]))
                elif "button" in turn:
                    action = f"button {turn['button']!r}"
                    replies = await session.tap_button(str(turn["button"]))
                else:
                    turn_results.append(
                        TurnResult(idx, "?", False, "turn must have send or button", elapsed_s=0)
                    )
                    all_passed = False
                    continue

                if "send" in turn and turn.get("button"):
                    btn = str(turn["button"])
                    action += f" + button {btn!r}"
                    replies.extend(await session.tap_button(btn))

                sandbox_inspect = sandbox_ctx.inspect() if sandbox_ctx else None
                expect = turn.get("expect") or {}
                traces = list(session.tool_traces)
                tools_called = [str(t["tool"]) for t in traces if t.get("tool")]
                ok, msg = _check_expectations(
                    expect,
                    replies=replies,
                    tool_traces=traces,
                    janitor_phase=session.janitor_phase(),
                    sandbox_inspect=sandbox_inspect,
                    llm_mode=llm_mode,
                )
                if not ok and self.verbose and tools_called:
                    msg = f"{msg}; tools called: {tools_called}"
                elapsed = time.perf_counter() - turn_t0
                turn_results.append(
                    TurnResult(
                        idx,
                        action,
                        ok,
                        msg,
                        replies=replies,
                        elapsed_s=elapsed,
                        tools_called=tools_called,
                    )
                )
                if not ok:
                    all_passed = False
        finally:
            if own_session and session is not None:
                await session.shutdown()
            if sandbox_ctx is not None:
                sandbox_ctx.__exit__(None, None, None)

        total = time.perf_counter() - t0
        return ScenarioResult(
            name=name,
            path=scenario_path,
            passed=all_passed,
            turns=turn_results,
            elapsed_s=total,
            llm_mode=llm_mode,
        )

    async def run_paths(self, paths: list[Path]) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        for path in sorted(paths):
            results.append(await self.run(path))
        return results

    def write_report(self, results: list[ScenarioResult], report_dir: Path) -> Path:
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
        out = report_dir / f"{stamp}-report.json"
        payload = {
            "passed": all(r.passed for r in results),
            "scenarios": [
                {
                    "name": r.name,
                    "path": str(r.path),
                    "passed": r.passed,
                    "elapsed_s": r.elapsed_s,
                    "llm_mode": r.llm_mode,
                    "turns": [
                        {
                            "index": t.index,
                            "action": t.action,
                            "passed": t.passed,
                            "message": t.message,
                            "elapsed_s": t.elapsed_s,
                            "tools_called": t.tools_called,
                        }
                        for t in r.turns
                    ],
                }
                for r in results
            ],
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out


def discover_scenarios(root: Path, suite: str | None = None) -> list[Path]:
    pattern = "**/*.yaml"
    paths = sorted(root.glob(pattern))
    if suite:
        paths = [p for p in paths if suite in p.parts]
    return paths


def discover_live_scenarios(root: Path, suite: str | None = None) -> list[Path]:
    """YAML scenarios with ``llm: live`` (OpenRouter required when not stubbed)."""
    return [
        p
        for p in discover_scenarios(root, suite=suite)
        if str(load_scenario(p).get("llm") or "live").lower() == "live"
    ]
