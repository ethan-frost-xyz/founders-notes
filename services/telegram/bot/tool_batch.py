"""Concurrent execution of multiple Librarian tool calls in one agent round."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from agent_tools import execute_tool
from config import AgentConfig
from telemetry import TelemetryCollector
from turn_timing import TurnTimer


@dataclass(frozen=True)
class ToolInvocation:
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolInvocationResult:
    invocation: ToolInvocation
    result: dict[str, Any]
    wall_ms: int


def _run_one(
    idx: int,
    invocation: ToolInvocation,
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None,
    timing: TurnTimer | None,
    telemetry: TelemetryCollector | None,
    on_tool_start: Callable[[str, dict[str, Any]], None] | None,
    tool_round: int | None,
) -> tuple[int, ToolInvocationResult]:
    if on_tool_start is not None:
        try:
            on_tool_start(invocation.name, invocation.arguments)
        except Exception:
            pass
    t0 = time.perf_counter()
    result = execute_tool(
        invocation.name,
        invocation.arguments,
        config=config,
        history=history,
        timing=timing,
        telemetry=telemetry,
        tool_round=tool_round,
    )
    wall_ms = int((time.perf_counter() - t0) * 1000)
    return idx, ToolInvocationResult(
        invocation=invocation,
        result=result,
        wall_ms=wall_ms,
    )


def execute_tool_batch(
    invocations: list[ToolInvocation],
    *,
    config: AgentConfig,
    history: list[dict[str, Any]] | None = None,
    timing: TurnTimer | None = None,
    telemetry: TelemetryCollector | None = None,
    on_tool_start: Callable[[str, dict[str, Any]], None] | None = None,
    tool_round: int | None = None,
) -> list[ToolInvocationResult]:
    """Run tool invocations concurrently when there are 2+; preserve input order."""
    if not invocations:
        return []

    common = {
        "config": config,
        "history": history,
        "timing": timing,
        "telemetry": telemetry,
        "on_tool_start": on_tool_start,
        "tool_round": tool_round,
    }

    if len(invocations) == 1:
        _, single = _run_one(0, invocations[0], **common)
        if timing is not None and tool_round is not None:
            timing.record_tool_batch(
                tool_round=tool_round,
                tools=[invocations[0].name],
                wall_ms=single.wall_ms,
                parallel=False,
            )
        return [single]

    t_batch = time.perf_counter()
    results: list[ToolInvocationResult | None] = [None] * len(invocations)
    with ThreadPoolExecutor(max_workers=len(invocations)) as ex:
        futures = [
            ex.submit(_run_one, i, inv, **common) for i, inv in enumerate(invocations)
        ]
        for fut in as_completed(futures):
            idx, payload = fut.result()
            results[idx] = payload
    batch_wall_ms = int((time.perf_counter() - t_batch) * 1000)
    if timing is not None:
        timing.add_thread_wait(batch_wall_ms)
        if tool_round is not None:
            timing.record_tool_batch(
                tool_round=tool_round,
                tools=[inv.name for inv in invocations],
                wall_ms=batch_wall_ms,
                parallel=True,
            )
    return [r for r in results if r is not None]
