"""Tests for timestamp estimation from transcript position."""

from __future__ import annotations

from timestamp_estimate import (
    apply_estimates_to_notes_body,
    estimate_bullet_timestamp,
    seconds_to_minute_timestamp,
)


def test_seconds_to_minute_timestamp():
    assert seconds_to_minute_timestamp(0) == "00:00"
    assert seconds_to_minute_timestamp(89) == "01:00"
    assert seconds_to_minute_timestamp(900) == "15:00"


def test_estimate_bullet_timestamp_known_offset():
    transcript = "a" * 1000 + "snow white took three years of seven day weeks" + "b" * 1000
    est = estimate_bullet_timestamp(
        "Snow White took three years of seven-day weeks",
        line="- — Snow White took three years",
        transcript_body=transcript,
        duration_seconds=3600,
        min_confidence=0.1,
    )
    assert est.suggested is not None
    minutes = int(est.suggested.split(":")[0])
    assert 25 <= minutes <= 35


def test_apply_estimates_to_notes_body():
    body = "## Raw datapoints\n\n- — lost timestamp bullet\n- 10:00 — already ok\n"
    est = estimate_bullet_timestamp(
        "lost timestamp bullet",
        line="- — lost timestamp bullet",
        transcript_body="intro lost timestamp bullet outro",
        duration_seconds=1200,
        min_confidence=0.1,
    )
    assert est.suggested
    updated = apply_estimates_to_notes_body(body, [est])
    assert est.suggested in updated
    assert "- — lost" not in updated
    assert "- 10:00 — already ok" in updated
