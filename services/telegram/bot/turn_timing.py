"""Per-turn timing telemetry for the Librarian pipeline."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TurnTiming:
    telegram_pickup_ms: int | None = None
    vault_search_local_ms: int = 0
    retrieval_llm_ms: int = 0
    searches: list[dict[str, Any]] = field(default_factory=list)
    openrouter_calls: list[dict[str, Any]] = field(default_factory=list)


class TurnTimer:
    """Thread-safe accumulator for one Librarian turn."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = TurnTiming()

    @property
    def telegram_pickup_ms(self) -> int | None:
        with self._lock:
            return self._data.telegram_pickup_ms

    def set_telegram_pickup_ms(self, ms: int) -> None:
        with self._lock:
            self._data.telegram_pickup_ms = ms

    def add_vault_local(self, ms: int) -> None:
        with self._lock:
            self._data.vault_search_local_ms += ms

    def add_retrieval_llm(self, ms: int) -> None:
        with self._lock:
            self._data.retrieval_llm_ms += ms

    def record_search(
        self,
        query: str,
        *,
        vault_search_local_ms: int = 0,
        retrieval_llm_ms: int = 0,
        tool: str | None = None,
        error: bool = False,
    ) -> None:
        with self._lock:
            row: dict[str, Any] = {
                "query": query,
                "vault_search_local_ms": vault_search_local_ms,
                "retrieval_llm_ms": retrieval_llm_ms,
            }
            if tool:
                row["tool"] = tool
            if error:
                row["error"] = True
            self._data.searches.append(row)

    def record_openrouter_stream(
        self,
        label: str,
        *,
        ttft_ms: int,
        total_ms: int,
        tokens: int,
    ) -> None:
        tok_per_sec: float | None = None
        gen_ms = total_ms - ttft_ms
        if tokens > 0 and gen_ms > 0:
            tok_per_sec = round(tokens / (gen_ms / 1000.0), 1)
        with self._lock:
            self._data.openrouter_calls.append(
                {
                    "label": label,
                    "ttft_ms": ttft_ms,
                    "total_ms": total_ms,
                    "completion_tokens": tokens,
                    "tok_per_sec": tok_per_sec,
                }
            )

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            d: dict[str, Any] = {
                "telegram_pickup_ms": self._data.telegram_pickup_ms,
                "vault_search_local_ms": self._data.vault_search_local_ms,
                "retrieval_llm_ms": self._data.retrieval_llm_ms,
                "searches": list(self._data.searches),
                "openrouter_calls": list(self._data.openrouter_calls),
            }
        calls = d["openrouter_calls"]
        if calls:
            ttfts = [c["ttft_ms"] for c in calls if c.get("ttft_ms") is not None]
            tok_rates = [c["tok_per_sec"] for c in calls if c.get("tok_per_sec") is not None]
            if ttfts:
                d["agent_ttft_ms_mean"] = round(sum(ttfts) / len(ttfts))
            if tok_rates:
                d["generation_tok_per_sec_mean"] = round(sum(tok_rates) / len(tok_rates), 1)
        return d

    def summary_line(self) -> str:
        return summary_line_from_dict(self.to_dict())


def summary_line_from_dict(d: dict[str, Any]) -> str:
    parts: list[str] = []
    pickup = d.get("telegram_pickup_ms")
    if pickup is not None:
        parts.append(f"pickup={pickup}ms")
    parts.append(f"vault={d.get('vault_search_local_ms', 0)}ms")
    parts.append(f"retrieval_llm={d.get('retrieval_llm_ms', 0)}ms")
    ttft = d.get("agent_ttft_ms_mean")
    if ttft is not None:
        parts.append(f"ttft={ttft}ms")
    tok = d.get("generation_tok_per_sec_mean")
    if tok is not None:
        parts.append(f"tok/s={tok}")
    return " ".join(parts)


def is_timing_enabled(*, harness: bool = False) -> bool:
    val = os.environ.get("LIBRARIAN_TIMING", "").strip()
    if harness:
        return val != "0"
    return val == "1"


def append_timing_jsonl(timing_dict: dict[str, Any], *, session_id: str | None = None) -> None:
    """Append one JSONL line on macOS production when LIBRARIAN_TIMING=1."""
    if sys.platform != "darwin":
        return
    path = Path.home() / "Library/Logs/founders-telegram/librarian-timing.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": time.time(), "session_id": session_id, **timing_dict}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")
