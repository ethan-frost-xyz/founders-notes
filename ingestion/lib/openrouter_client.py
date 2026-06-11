"""OpenRouter chat completions: sync, streaming, retries."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from expand_validate import count_datapoint_headings_in_partial

OPENROUTER_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class OpenRouterCompletion:
    content: str
    response_id: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    duration_ms: int


class ExpandProgressReporter(Protocol):
    """Optional live progress callbacks during a streaming expand call."""

    def waiting(self, *, input_chars: int) -> None: ...

    def first_token(self, *, ttft_ms: int) -> None: ...

    def section(self, *, index: int, total: int) -> None: ...


def usage_from_response(response: Any) -> dict[str, Any]:
    """Normalize OpenRouter/OpenAI usage fields from a chat completion response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": None,
        }
    prompt_tokens = int(getattr(usage, "prompt_tokens", None) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", None) or 0)
    total_tokens = int(getattr(usage, "total_tokens", None) or 0)
    if total_tokens == 0 and (prompt_tokens or completion_tokens):
        total_tokens = prompt_tokens + completion_tokens
    cost_raw = getattr(usage, "cost", None)
    cost_usd: float | None
    if cost_raw is None:
        cost_usd = None
    else:
        try:
            cost_usd = float(cost_raw)
        except (TypeError, ValueError):
            cost_usd = None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
    }


def _openrouter_retry_delay_sec(failed_attempt: int) -> float:
    """Seconds to wait after failed attempt N (1-based) before the next try."""
    return min(2.0 ** (failed_attempt - 1), 30.0)


def is_retriable_openrouter_error(exc: Exception) -> bool:
    """True for transient API/network failures worth retrying."""
    if isinstance(exc, ValueError) and "empty model response" in str(exc).lower():
        return True
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )
    except ImportError:
        return False
    if isinstance(
        exc,
        (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError),
    ):
        return True
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None)
        if code is None:
            return False
        return int(code) in (408, 429, 500, 502, 503, 504)
    return False


def execute_openrouter_with_retry(
    operation: Callable[[], OpenRouterCompletion],
    *,
    max_attempts: int = OPENROUTER_MAX_ATTEMPTS,
    episode_id: str | None = None,
    on_retry: Callable[[int, int, int], None] | None = None,
) -> OpenRouterCompletion:
    """Run an OpenRouter call up to max_attempts times on retriable errors."""
    prefix = f"[expand] {episode_id}  " if episode_id else "[expand] "
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            t0 = time.perf_counter()
            return operation()
        except Exception as e:
            failed_call_ms = int((time.perf_counter() - t0) * 1000)
            last_exc = e
            if attempt >= max_attempts or not is_retriable_openrouter_error(e):
                raise
            delay = _openrouter_retry_delay_sec(attempt)
            print(
                f"{prefix}API attempt {attempt}/{max_attempts} failed "
                f"({type(e).__name__}: {e}); retrying in {delay:.0f}s…",
                flush=True,
            )
            sleep_start = time.perf_counter()
            time.sleep(delay)
            sleep_ms = int((time.perf_counter() - sleep_start) * 1000)
            if on_retry is not None:
                on_retry(attempt, sleep_ms, failed_call_ms)
    assert last_exc is not None
    raise last_exc


def call_openrouter(
    *,
    system: str,
    user: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.0,
    response_format: dict[str, str] | None = None,
    episode_id: str | None = None,
    on_complete: Callable[[OpenRouterCompletion], None] | None = None,
    on_retry: Callable[[int, int, int], None] | None = None,
) -> OpenRouterCompletion:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=(base_url or "https://openrouter.ai/api/v1").rstrip("/"),
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    def _once() -> OpenRouterCompletion:
        t0 = time.perf_counter()
        response = client.chat.completions.create(**kwargs)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("empty model response")
        usage = usage_from_response(response)
        return OpenRouterCompletion(
            content=raw,
            response_id=getattr(response, "id", None),
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=usage["cost_usd"],
            duration_ms=duration_ms,
        )

    result = execute_openrouter_with_retry(
        _once,
        episode_id=episode_id,
        on_retry=on_retry,
    )
    if on_complete is not None:
        on_complete(result)
    return result


def call_openrouter_streaming(
    *,
    system: str,
    user: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.0,
    total_sections: int = 0,
    reporter: ExpandProgressReporter | None = None,
    episode_id: str | None = None,
) -> OpenRouterCompletion:
    """Stream chat completion; optional reporter for TTFT and per-section progress."""
    from openai import OpenAI

    if reporter is not None:
        reporter.waiting(input_chars=len(system) + len(user))

    client = OpenAI(
        api_key=api_key,
        base_url=(base_url or "https://openrouter.ai/api/v1").rstrip("/"),
    )

    def _once() -> OpenRouterCompletion:
        t0 = time.perf_counter()
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )

        parts: list[str] = []
        response_id: str | None = None
        usage_chunk: Any = None
        first_token_reported = False
        last_section_count = 0
        section_total = max(total_sections, 0)

        for chunk in stream:
            chunk_id = getattr(chunk, "id", None)
            if chunk_id:
                response_id = chunk_id
            if getattr(chunk, "usage", None) is not None:
                usage_chunk = chunk

            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if not delta:
                continue

            if not first_token_reported:
                if reporter is not None:
                    reporter.first_token(ttft_ms=int((time.perf_counter() - t0) * 1000))
                first_token_reported = True

            parts.append(delta)
            buffer = "".join(parts)
            n_sections = count_datapoint_headings_in_partial(buffer)
            if reporter is not None and n_sections > last_section_count:
                for idx in range(last_section_count + 1, n_sections + 1):
                    reporter.section(
                        index=idx,
                        total=section_total if section_total > 0 else n_sections,
                    )
                last_section_count = n_sections

        duration_ms = int((time.perf_counter() - t0) * 1000)
        raw = "".join(parts)
        if not raw:
            raise ValueError("empty model response")

        usage = (
            usage_from_response(usage_chunk)
            if usage_chunk is not None
            else usage_from_response(None)
        )
        return OpenRouterCompletion(
            content=raw,
            response_id=response_id,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=usage["cost_usd"],
            duration_ms=duration_ms,
        )

    return execute_openrouter_with_retry(_once, episode_id=episode_id)
