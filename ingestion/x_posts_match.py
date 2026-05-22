"""Episode attribution scoring for X posts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

EP_MENTION_RE = re.compile(
    r"(?:Founders:?\s*)?(?:#|ep(?:isode)?\.?\s*)(\d{1,4})\b",
    re.IGNORECASE,
)
AUTO_ACCEPT_SCORE = 0.75
REVIEW_SCORE = 0.5


def days_between(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        da = datetime.strptime(a[:10], "%Y-%m-%d")
        db = datetime.strptime(b[:10], "%Y-%m-%d")
        return abs((da - db).days)
    except ValueError:
        return None


def title_tokens(title: str) -> set[str]:
    t = re.sub(r"^#\d+[:\s]+", "", title, flags=re.IGNORECASE)
    return set(re.findall(r"[a-z]{4,}", t.lower()))


def match_episode(
    text: str,
    post_date: str | None,
    rows_by_number: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, float, str]:
    mentions = [int(m.group(1)) for m in EP_MENTION_RE.finditer(text)]
    if mentions:
        num = mentions[0]
        row = rows_by_number.get(num)
        if row:
            return row, 0.95, f"explicit_mention_{num}"

    text_lower = text.lower()
    best: tuple[dict[str, Any] | None, float, str] = (None, 0.0, "none")

    for num, row in rows_by_number.items():
        title = row.get("title") or ""
        tokens = title_tokens(title)
        if not tokens:
            continue
        hits = sum(1 for tok in tokens if tok in text_lower)
        if hits >= 2:
            score = min(0.7, 0.35 + hits * 0.1)
            pub = row.get("published_at")
            delta = days_between(post_date, pub)
            if delta is not None and delta <= 14:
                score = min(0.85, score + 0.2)
            if score > best[1]:
                best = (row, score, f"title_tokens_{hits}")

    if best[0] and post_date:
        row = best[0]
        delta = days_between(post_date, row.get("published_at"))
        if delta is not None and delta <= 7 and best[1] < 0.8:
            return row, 0.72, "date_proximity"

    return best
