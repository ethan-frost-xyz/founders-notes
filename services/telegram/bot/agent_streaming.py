"""Stream aggregation for OpenRouter chat completions."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, Callable

from turn_timing import TurnTimer


def accumulate_streamed_message(
    stream: Any,
    *,
    on_chunk: Callable[[str], None] | None,
    timing: TurnTimer | None = None,
    label: str = "agent",
    span_name: str | None = None,
) -> SimpleNamespace:
    t0 = time.perf_counter()
    first_token_at: float | None = None
    content_parts: list[str] = []
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    usage_completion_tokens = 0

    for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            usage = chunk.usage
            usage_completion_tokens = int(getattr(usage, "completion_tokens", None) or 0)
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        has_token = bool(delta.content) or bool(delta.tool_calls)
        if has_token and first_token_at is None:
            first_token_at = time.perf_counter()
        if delta.content:
            content_parts.append(delta.content)
            if on_chunk is not None:
                on_chunk(delta.content)
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                slot = tool_calls_acc.setdefault(
                    idx,
                    {"id": "", "name": "", "arguments_parts": []},
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function.arguments:
                        slot["arguments_parts"].append(tc.function.arguments)

    t_end = time.perf_counter()
    if timing is not None and first_token_at is not None:
        content = "".join(content_parts)
        tokens = usage_completion_tokens or max(1, len(content) // 4)
        timing.record_openrouter_stream(
            label,
            ttft_ms=int((first_token_at - t0) * 1000),
            total_ms=int((t_end - t0) * 1000),
            tokens=tokens,
            span_name=span_name,
        )

    tool_calls = None
    if tool_calls_acc:
        tool_calls = []
        for idx in sorted(tool_calls_acc):
            slot = tool_calls_acc[idx]
            tool_calls.append(
                SimpleNamespace(
                    id=slot["id"] or f"call_{idx}",
                    function=SimpleNamespace(
                        name=slot["name"],
                        arguments="".join(slot["arguments_parts"]),
                    ),
                )
            )

    return SimpleNamespace(
        content="".join(content_parts) if content_parts else None,
        tool_calls=tool_calls,
    )
