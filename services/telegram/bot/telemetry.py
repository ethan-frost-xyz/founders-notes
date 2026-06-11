"""Flexible per-turn telemetry for the Librarian agent and retrieval pipeline."""

from __future__ import annotations

import threading
import time
from typing import Any, Protocol

MAX_SPANS_PER_TURN = 200


class TelemetryCollector(Protocol):
    def span(self, name: str, *, attrs: dict[str, Any] | None = None) -> SpanContext: ...

    def record_event(self, name: str, *, attrs: dict[str, Any] | None = None) -> None: ...

    def record_phase(self, name: str, ms: int, *, attrs: dict[str, Any] | None = None) -> None: ...


class NoOpSpanContext:
    def __enter__(self) -> NoOpSpanContext:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class NoOpCollector:
    """Zero-cost collector used when timing is disabled."""

    def span(self, name: str, *, attrs: dict[str, Any] | None = None) -> NoOpSpanContext:
        _ = name, attrs
        return NoOpSpanContext()

    def record_event(self, name: str, *, attrs: dict[str, Any] | None = None) -> None:
        _ = name, attrs

    def record_phase(self, name: str, ms: int, *, attrs: dict[str, Any] | None = None) -> None:
        _ = name, ms, attrs


class SpanContext:
    """Context manager that records wall time for a named span on exit."""

    __slots__ = ("_collector", "_name", "_attrs", "_t0")

    def __init__(
        self,
        collector: TurnTimerCollector,
        name: str,
        *,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        self._collector = collector
        self._name = name
        self._attrs = dict(attrs or {})
        self._t0 = 0.0

    def __enter__(self) -> SpanContext:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        ms = int((time.perf_counter() - self._t0) * 1000)
        self._collector._append_span(self._name, ms, self._attrs)


class TurnTimerCollector:
    """Records spans and phase events for harness observability."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spans: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []

    def span(self, name: str, *, attrs: dict[str, Any] | None = None) -> SpanContext:
        return SpanContext(self, name, attrs=attrs)

    def record_event(self, name: str, *, attrs: dict[str, Any] | None = None) -> None:
        row: dict[str, Any] = {"name": name}
        if attrs:
            row["attrs"] = dict(attrs)
        with self._lock:
            if len(self._events) < MAX_SPANS_PER_TURN:
                self._events.append(row)

    def record_phase(self, name: str, ms: int, *, attrs: dict[str, Any] | None = None) -> None:
        extra = dict(attrs or {})
        self._append_span(name, ms, extra)

    def _append_span(self, name: str, ms: int, attrs: dict[str, Any]) -> None:
        row: dict[str, Any] = {"name": name, "ms": ms}
        if attrs:
            row["attrs"] = attrs
        with self._lock:
            if len(self._spans) < MAX_SPANS_PER_TURN:
                self._spans.append(row)

    def to_trace_record(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._spans and not self._events:
                return None
            out: dict[str, Any] = {"record": "spans", "spans": list(self._spans)}
            if self._events:
                out["events"] = list(self._events)
            return out


NO_OP_COLLECTOR = NoOpCollector()
