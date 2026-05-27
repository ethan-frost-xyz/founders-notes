"""Episode id parsing and notes body helpers for Janitor (clean is LLM-only)."""

from __future__ import annotations

import re

from episode_ids import format_episode_id, parse_numbered_episode_id

RAW_SECTION = "## Raw datapoints"

EPISODE_ID_RE = re.compile(r"\b(ep-?\d{1,4})\b", re.IGNORECASE)
EPISODE_NUM_RE = re.compile(r"(?:^|\s)(?:#|episode\s*)?(\d{1,4})\b", re.IGNORECASE)


def parse_episode_id(text: str) -> str | None:
    """Return canonical ep-NNNN from free text, or None."""
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    stripped = first_line.strip() or text.strip()
    m = EPISODE_ID_RE.search(stripped)
    if m:
        token = m.group(1).lower()
        if not token.startswith("ep-"):
            token = "ep-" + token.removeprefix("ep")
        num = parse_numbered_episode_id(token)
        if num is not None:
            return format_episode_id(num)
    m = EPISODE_NUM_RE.search(stripped)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 9999:
            return format_episode_id(num)
    return None


def finalize_notes_body(text: str) -> tuple[str, list[str]]:
    """Light wrap of LLM output — no rigid re-parse of the paste."""
    warnings: list[str] = []
    stripped = text.strip()
    if not stripped:
        return f"{RAW_SECTION}\n\n", ["Empty LLM output."]

    if RAW_SECTION not in stripped:
        bullet_lines = [ln.rstrip() for ln in stripped.splitlines() if ln.strip().startswith("- ")]
        if bullet_lines:
            stripped = f"{RAW_SECTION}\n\n" + "\n".join(bullet_lines)
        else:
            warnings.append("LLM output missing ## Raw datapoints header.")
            stripped = f"{RAW_SECTION}\n\n{stripped}"

    if not stripped.endswith("\n"):
        stripped += "\n"
    if not extract_bullet_lines(stripped):
        warnings.append("No `- timestamp` bullets in cleaned output.")
    return stripped, warnings


def extract_bullet_lines(body: str) -> list[str]:
    lines: list[str] = []
    in_section = False
    for line in body.splitlines():
        if line.strip() == RAW_SECTION:
            in_section = True
            continue
        if in_section and line.strip().startswith("- "):
            lines.append(line.rstrip())
    return lines


def merge_notes_body(existing_body: str, new_body: str) -> str:
    """Append new timestamp bullets under ## Raw datapoints."""
    new_lines = extract_bullet_lines(new_body)

    if RAW_SECTION not in existing_body:
        base = existing_body.rstrip()
        if base:
            return base + "\n\n" + RAW_SECTION + "\n\n" + "\n".join(new_lines) + "\n"
        return RAW_SECTION + "\n\n" + "\n".join(new_lines) + "\n"

    parts = existing_body.split(RAW_SECTION, 1)
    head = parts[0].rstrip()
    existing_bullets = extract_bullet_lines(existing_body)
    merged = existing_bullets + [ln for ln in new_lines if ln not in existing_bullets]
    return head + "\n\n" + RAW_SECTION + "\n\n" + "\n".join(merged) + "\n"
