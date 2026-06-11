"""YAML scenario loader and assertion engine for the mock Telegram harness."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from harness.janitor_sandbox import JanitorSandbox
from harness.mock_session import MockBotSession, Reply
from harness.response_report import HarnessReportPaths, write_response_markdown
from harness.observability import aggregate_observability
from harness.report_meta import REPORT_SCHEMA_VERSION, harness_git_sha
from harness.trace_report import enrich_turn_from_traces

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

_EPISODE_CITATION_RE = re.compile(r"\[ep-\d{4}\]")


@dataclass
class TurnResult:
    index: int
    action: str
    passed: bool
    message: str
    replies: list[Reply] = field(default_factory=list)
    elapsed_s: float = 0.0
    tools_called: list[str] = field(default_factory=list)
    timing: dict[str, Any] | None = None
    timing_summary: str | None = None
    response_text: str = ""
    stop_reason: str = "natural"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_rounds: list[dict[str, Any]] = field(default_factory=list)
    tool_call_counts: dict[str, int] = field(default_factory=dict)
    trace_summary: str = ""
    timing_accountability: dict[str, Any] | None = None
    observability: dict[str, Any] | None = None
    user_send: str = ""


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
        cap_note = ""
        if any(t.stop_reason == "cap" for t in self.turns):
            cap_note = " cap"
        path_note = ""
        if verbose and self.turns:
            obs = self.turns[0].observability or {}
            path_str = (obs.get("agent_path") or {}).get("path_string") or ""
            if path_str:
                path_note = f" | path: {path_str}"
        lines = [
            f"{status}  {self.name}  ({self.elapsed_s:.1f}s, {self.llm_mode}){cap_note}{path_note}"
        ]
        for turn in self.turns:
            mark = "ok" if turn.passed else "FAIL"
            line = f"  [{mark}] turn {turn.index}: {turn.action} — {turn.message}"
            if verbose and turn.tools_called:
                line += f" (tools: {', '.join(turn.tools_called)})"
            if verbose and turn.timing_summary:
                line += f" [{turn.timing_summary}]"
            if verbose and turn.stop_reason == "cap":
                line += " [cap]"
            if verbose and turn.timing_accountability:
                unaccounted = int(turn.timing_accountability.get("unaccounted_ms") or 0)
                if unaccounted > 30_000:
                    line += f" [unaccounted={unaccounted}ms]"
            if verbose and turn.observability:
                line += _format_observability_verbose_line(turn.observability)
            lines.append(line)
        return "\n".join(lines)


def _timing_from_traces(traces: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    for entry in reversed(traces):
        if entry.get("record") == "timing":
            timing = {k: v for k, v in entry.items() if k != "record"}
            try:
                from turn_timing import summary_line_from_dict

                summary = summary_line_from_dict(timing)
            except ImportError:
                summary = None
            return timing, summary
    return None, None


def aggregate_timing(results: list[ScenarioResult]) -> dict[str, Any]:
    """Mean/sum across all turns that recorded timing."""
    turns_with_timing: list[dict[str, Any]] = []
    for result in results:
        for turn in result.turns:
            if turn.timing:
                turns_with_timing.append(turn.timing)

    if not turns_with_timing:
        return {"turn_count": 0}

    def _sum(key: str) -> int:
        return sum(int(t.get(key) or 0) for t in turns_with_timing)

    def _mean(key: str) -> float | None:
        vals = [t.get(key) for t in turns_with_timing if t.get(key) is not None]
        if not vals:
            return None
        return round(sum(float(v) for v in vals) / len(vals), 1)

    pickup_vals = [t["telegram_pickup_ms"] for t in turns_with_timing if t.get("telegram_pickup_ms") is not None]

    return {
        "turn_count": len(turns_with_timing),
        "sum_vault_search_local_ms": _sum("vault_search_local_ms"),
        "sum_retrieval_llm_ms": _sum("retrieval_llm_ms"),
        "mean_vault_search_local_ms": _mean("vault_search_local_ms"),
        "mean_retrieval_llm_ms": _mean("retrieval_llm_ms"),
        "mean_agent_ttft_ms": _mean("agent_ttft_ms_mean"),
        "mean_generation_tok_per_sec": _mean("generation_tok_per_sec_mean"),
        "mean_telegram_pickup_ms": (
            round(sum(pickup_vals) / len(pickup_vals), 1) if pickup_vals else None
        ),
    }


def _harness_timing_enabled() -> bool:
    return os.environ.get("LIBRARIAN_TIMING", "").strip() != "0"


def _format_observability_verbose_line(obs: dict[str, Any]) -> str:
    if not obs.get("timing_enabled"):
        return ""
    latency = obs.get("latency") or {}
    retrieval = latency.get("retrieval") or {}
    parts: list[str] = []
    routing = latency.get("agent_routing_ms")
    if routing is not None:
        parts.append(f"routing={routing / 1000:.1f}s")
    for key in ("query_expand_ms", "hybrid_search_ms", "llm_rerank_ms"):
        val = retrieval.get(key)
        if val:
            short = key.replace("_ms", "").replace("query_expand", "expand").replace("hybrid_search", "hybrid").replace("llm_rerank", "rerank")
            parts.append(f"{short}={val / 1000:.1f}s")
    synth = latency.get("synthesis") or {}
    if synth.get("final_ttft_ms") is not None:
        parts.append(f"final_ttft={synth['final_ttft_ms'] / 1000:.1f}s")
    cap_thrash = obs.get("cap_thrash") or {}
    gathered = cap_thrash.get("gathered") or {}
    if gathered.get("thrash_score") is not None:
        parts.append(f"thrash={gathered['thrash_score']}")
    if not parts:
        return ""
    return f"\n    latency: {' '.join(parts)}"


def format_timing_aggregate(agg: dict[str, Any]) -> str:
    if not agg.get("turn_count"):
        return "Timing: no turns recorded timing data."
    lines = [
        f"Timing aggregate ({agg['turn_count']} turns):",
        f"  vault_local  mean={agg.get('mean_vault_search_local_ms')}ms  sum={agg.get('sum_vault_search_local_ms')}ms",
        f"  retrieval_llm mean={agg.get('mean_retrieval_llm_ms')}ms  sum={agg.get('sum_retrieval_llm_ms')}ms",
    ]
    if agg.get("mean_agent_ttft_ms") is not None:
        lines.append(f"  agent_ttft   mean={agg['mean_agent_ttft_ms']}ms")
    if agg.get("mean_generation_tok_per_sec") is not None:
        lines.append(f"  tok/s        mean={agg['mean_generation_tok_per_sec']}")
    if agg.get("mean_telegram_pickup_ms") is not None:
        lines.append(f"  pickup       mean={agg['mean_telegram_pickup_ms']}ms")
    if agg.get("mean_final_ttft_ms") is not None:
        lines.append(f"  final_ttft   mean={agg['mean_final_ttft_ms']}ms")
    if agg.get("cap_hits") is not None:
        lines.append(f"  cap_hits     {agg['cap_hits']}")
    if agg.get("mean_thrash_score") is not None:
        lines.append(f"  thrash_score mean={agg['mean_thrash_score']}")
    return "\n".join(lines)


def aggregate_scenario_observability(results: list[ScenarioResult]) -> dict[str, Any]:
    turn_rows: list[dict[str, Any]] = []
    for result in results:
        for turn in result.turns:
            if turn.observability:
                turn_rows.append({"observability": turn.observability})
    agg = aggregate_observability(turn_rows)
    if not agg:
        return {}
    agg["pass_count"] = sum(1 for r in results if r.passed)
    agg["scenario_count"] = len(results)
    agg["mean_wall_s"] = round(sum(r.elapsed_s for r in results) / len(results), 1) if results else 0
    agg["cap_hits"] = sum(
        1 for r in results for t in r.turns if t.stop_reason == "cap"
    )
    return agg


def detect_suite_from_results(results: list[ScenarioResult]) -> str | None:
    if not results:
        return None
    if all("librarian" in r.path.parts for r in results):
        return "librarian"
    if all("janitor" in r.path.parts for r in results):
        return "janitor"
    return None


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

    not_contains_all = expect.get("not_contains_all")
    if not_contains_all:
        for needle in not_contains_all:
            needle_s = str(needle)
            if needle_s in combined:
                return False, f"expected reply not to contain {needle_s!r}"

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
        names = [str(t["tool"]) for t in tool_traces if t.get("tool")]
        if tool_called not in names:
            return False, f"expected tool {tool_called!r}, got {names!r}"

    tool_called_any = merged.get("tool_called_any")
    if tool_called_any and llm_mode == "live":
        expected_any = [str(x) for x in tool_called_any]
        names = [str(t["tool"]) for t in tool_traces if t.get("tool")]
        if not any(tool in names for tool in expected_any):
            return False, f"expected one of {expected_any!r}, got {names!r}"

    response_contains = merged.get("response_contains")
    if response_contains and llm_mode == "live":
        if str(response_contains) not in combined:
            return False, f"expected response to contain {response_contains!r}"

    response_any = merged.get("response_contains_any")
    if response_any and llm_mode == "live":
        needles = [str(x) for x in response_any]
        if not any(n in combined for n in needles):
            return False, f"expected response to contain one of {needles!r}"

    if merged.get("response_contains_episode_citation") and llm_mode == "live":
        if not _EPISODE_CITATION_RE.search(combined):
            return False, "expected response to contain episode citation [ep-NNNN]"

    status_contains = merged.get("status_contains")
    if status_contains and llm_mode == "live":
        needle = str(status_contains)
        if needle not in combined:
            return False, f"expected a status reply containing {needle!r}"

    tools_called_expect = merged.get("tools_called")
    if tools_called_expect and llm_mode == "live":
        expected_tools = [str(x) for x in tools_called_expect]
        names = [str(t["tool"]) for t in tool_traces if t.get("tool")]
        for tool in expected_tools:
            if tool not in names:
                return False, f"expected tools {expected_tools!r}, got {names!r}"

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
                user_send = str(turn["send"]) if "send" in turn else ""

                if "send" in turn:
                    action = f"send {turn['send']!r}"
                    session.tool_traces.clear()
                    replies = await session.send(user_send)
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
                enriched = enrich_turn_from_traces(
                    traces,
                    replies,
                    elapsed_s=elapsed,
                    llm_mode=llm_mode,
                    assistant_content=session.last_assistant_content,
                    timing_enabled=_harness_timing_enabled(),
                )
                turn_results.append(
                    TurnResult(
                        idx,
                        action,
                        ok,
                        msg,
                        replies=replies,
                        elapsed_s=elapsed,
                        tools_called=tools_called,
                        timing=enriched.get("timing"),
                        timing_summary=enriched.get("timing_summary"),
                        response_text=str(enriched.get("response_text") or ""),
                        stop_reason=str(enriched.get("stop_reason") or "natural"),
                        tool_calls=list(enriched.get("tool_calls") or []),
                        tool_rounds=list(enriched.get("tool_rounds") or []),
                        tool_call_counts=dict(enriched.get("tool_call_counts") or {}),
                        trace_summary=str(enriched.get("trace_summary") or ""),
                        timing_accountability=enriched.get("timing_accountability"),
                        observability=enriched.get("observability"),
                        user_send=user_send,
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

    def _turn_report_dict(self, turn: TurnResult) -> dict[str, Any]:
        row: dict[str, Any] = {
            "index": turn.index,
            "action": turn.action,
            "passed": turn.passed,
            "message": turn.message,
            "elapsed_s": turn.elapsed_s,
            "tools_called": turn.tools_called,
            "response_text": turn.response_text,
            "stop_reason": turn.stop_reason,
            "tool_calls": turn.tool_calls,
            "tool_rounds": turn.tool_rounds,
            "tool_call_counts": turn.tool_call_counts,
            "trace_summary": turn.trace_summary,
        }
        if turn.timing is not None:
            row["timing"] = turn.timing
        if turn.timing_summary:
            row["timing_summary"] = turn.timing_summary
        if turn.timing_accountability is not None:
            row["timing_accountability"] = turn.timing_accountability
        if turn.observability is not None:
            row["observability"] = turn.observability
        return row

    def write_report(
        self,
        results: list[ScenarioResult],
        report_dir: Path,
        *,
        repo_root: Path | None = None,
    ) -> HarnessReportPaths:
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
        json_path = report_dir / f"{stamp}-report.json"
        root = repo_root or report_dir.parents[3]
        aggregate = aggregate_scenario_observability(results)
        payload: dict[str, Any] = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "harness_version": harness_git_sha(root),
            "suite": detect_suite_from_results(results),
            "passed": all(r.passed for r in results),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scenario_count": len(results),
            "scenarios": [
                {
                    "name": r.name,
                    "path": str(r.path),
                    "passed": r.passed,
                    "elapsed_s": r.elapsed_s,
                    "llm_mode": r.llm_mode,
                    "turns": [self._turn_report_dict(t) for t in r.turns],
                }
                for r in results
            ],
        }
        if aggregate:
            payload["aggregate"] = aggregate
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path = write_response_markdown(results, report_dir, stamp=stamp)
        return HarnessReportPaths(json=json_path, markdown=md_path)


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


def paths_need_live_llm(paths: list[Path], *, stub_llm: bool) -> bool:
    """True if any selected scenario runs with OpenRouter (not echo/stub)."""
    if stub_llm:
        return False
    for path in paths:
        file_llm = str(load_scenario(path).get("llm") or "live").lower()
        if file_llm != "echo":
            return True
    return False
