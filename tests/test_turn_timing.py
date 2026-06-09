"""Unit tests for Librarian turn timing telemetry."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from turn_timing import (
    TurnTimer,
    append_timing_jsonl,
    is_timing_enabled,
    summary_line_from_dict,
)


def test_is_timing_enabled_harness_default_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LIBRARIAN_TIMING", raising=False)
    assert is_timing_enabled(harness=True) is True


def test_is_timing_enabled_harness_opt_out(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIBRARIAN_TIMING", "0")
    assert is_timing_enabled(harness=True) is False


def test_is_timing_enabled_production_default_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LIBRARIAN_TIMING", raising=False)
    assert is_timing_enabled(harness=False) is False


def test_is_timing_enabled_production_opt_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIBRARIAN_TIMING", "1")
    assert is_timing_enabled(harness=False) is True


def test_timer_aggregates_buckets():
    timer = TurnTimer()
    timer.set_telegram_pickup_ms(120)
    timer.add_vault_local(50)
    timer.add_retrieval_llm(200)
    timer.record_search("Rockefeller", vault_search_local_ms=50, retrieval_llm_ms=200)
    timer.record_openrouter_stream(
        "agent_round_1",
        ttft_ms=300,
        total_ms=1500,
        tokens=100,
    )
    d = timer.to_dict()
    assert d["telegram_pickup_ms"] == 120
    assert d["vault_search_local_ms"] == 50
    assert d["retrieval_llm_ms"] == 200
    assert len(d["searches"]) == 1
    assert d["agent_ttft_ms_mean"] == 300
    assert d["generation_tok_per_sec_mean"] == pytest.approx(83.3, rel=0.05)


def test_summary_line():
    d = {
        "telegram_pickup_ms": None,
        "vault_search_local_ms": 100,
        "retrieval_llm_ms": 400,
        "agent_ttft_ms_mean": 250,
        "generation_tok_per_sec_mean": 42.0,
    }
    line = summary_line_from_dict(d)
    assert "vault=100ms" in line
    assert "retrieval_llm=400ms" in line
    assert "ttft=250ms" in line
    assert "tok/s=42.0" in line
    assert "pickup" not in line


def test_timer_thread_safe_concurrent_adds():
    timer = TurnTimer()
    n = 50

    def worker() -> None:
        for _ in range(n):
            timer.add_vault_local(1)
            timer.add_retrieval_llm(1)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda _: worker(), range(8)))

    d = timer.to_dict()
    assert d["vault_search_local_ms"] == 8 * n
    assert d["retrieval_llm_ms"] == 8 * n


def test_append_timing_jsonl_skips_non_darwin(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr("turn_timing.sys.platform", "linux")
    append_timing_jsonl({"vault_search_local_ms": 1}, session_id="test")
    assert not (tmp_path / "librarian-timing.jsonl").exists()


def test_append_timing_jsonl_writes_on_darwin(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr("turn_timing.sys.platform", "darwin")
    log_dir = tmp_path / "Library" / "Logs" / "founders-telegram"
    monkeypatch.setattr("turn_timing.Path.home", lambda: tmp_path)
    append_timing_jsonl({"vault_search_local_ms": 42}, session_id="s1")
    out = log_dir / "librarian-timing.jsonl"
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "vault_search_local_ms" in text
    assert "s1" in text
