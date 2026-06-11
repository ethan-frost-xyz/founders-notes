"""Estimate MM:SS timestamps for notes bullets missing timestamps."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from markdown_io import LOST_TIMESTAMP_BULLET_RE, read_markdown_body

_STOPWORDS = frozenset(
    {"the", "and", "for", "that", "with", "from", "this", "they", "were", "have", "was", "not"}
)


@dataclass(frozen=True)
class TimestampEstimate:
    bullet_text: str
    line: str
    suggested: str | None
    confidence: float
    reason: str | None = None


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"[^a-z0-9\s]", " ", lowered)


def _needle_words(bullet_text: str, *, max_words: int = 8) -> str:
    words = [w for w in _normalize_text(bullet_text).split() if len(w) >= 3 and w not in _STOPWORDS]
    if not words:
        words = [w for w in _normalize_text(bullet_text).split() if w]
    return " ".join(words[:max_words]).strip()


def _match_offset(transcript: str, bullet_text: str) -> tuple[int, float]:
    needle = _needle_words(bullet_text)
    if not needle:
        return 0, 0.0
    hay = _normalize_text(transcript)
    idx = hay.find(needle)
    if idx >= 0:
        return idx, min(1.0, len(needle) / max(len(hay), 1) + 0.5)

    best_ratio = 0.0
    best_pos = 0
    window = len(needle) + 40
    step = max(20, len(needle) // 2)
    for start in range(0, max(1, len(hay) - window), step):
        chunk = hay[start : start + window]
        ratio = SequenceMatcher(None, needle, chunk).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_pos = start
    return best_pos, best_ratio


def seconds_to_minute_timestamp(total_seconds: int) -> str:
    minutes = max(0, round(total_seconds / 60))
    return f"{minutes:02d}:00"


def estimate_bullet_timestamp(
    bullet_text: str,
    *,
    line: str,
    transcript_body: str,
    duration_seconds: int,
    min_confidence: float = 0.35,
) -> TimestampEstimate:
    if duration_seconds <= 0:
        return TimestampEstimate(
            bullet_text=bullet_text,
            line=line,
            suggested=None,
            confidence=0.0,
            reason="missing duration_seconds",
        )
    offset, confidence = _match_offset(transcript_body, bullet_text)
    if confidence < min_confidence:
        return TimestampEstimate(
            bullet_text=bullet_text,
            line=line,
            suggested=None,
            confidence=confidence,
            reason="below min confidence",
        )
    ratio = offset / max(len(_normalize_text(transcript_body)), 1)
    estimated_sec = int(ratio * duration_seconds)
    ts = seconds_to_minute_timestamp(estimated_sec)
    return TimestampEstimate(
        bullet_text=bullet_text,
        line=line,
        suggested=ts,
        confidence=confidence,
    )


def iter_lost_timestamp_bullets(notes_body: str) -> list[tuple[str, str]]:
    """Return (full_line, bullet_text) for each lost-timestamp bullet."""
    out: list[tuple[str, str]] = []
    for m in LOST_TIMESTAMP_BULLET_RE.finditer(notes_body):
        line = m.group(0)
        text = re.sub(r"^[\s]*-\s*[-–—]\s*", "", line).strip()
        out.append((line, text))
    return out


def apply_estimates_to_notes_body(
    notes_body: str,
    estimates: list[TimestampEstimate],
) -> str:
    updated = notes_body
    for est in estimates:
        if not est.suggested:
            continue
        new_line = f"- {est.suggested} — {est.bullet_text}"
        updated = updated.replace(est.line, new_line, 1)
    return updated
