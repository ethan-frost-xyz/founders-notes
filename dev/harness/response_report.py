"""Markdown response reports for live librarian harness runs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness.scenario_runner import ScenarioResult


def _is_librarian_scenario(path: Path) -> bool:
    return "librarian" in path.parts


def _blockquote_lines(text: str) -> list[str]:
    lines = text.splitlines() or [text]
    return [f"> {line}" if line else ">" for line in lines]


def format_response_markdown(results: list[ScenarioResult]) -> str | None:
    """Build markdown body for live librarian scenarios, or None if not applicable."""
    librarian_live = [
        r
        for r in results
        if r.llm_mode == "live" and _is_librarian_scenario(r.path)
    ]
    if not librarian_live:
        return None

    overall = "PASS" if all(r.passed for r in librarian_live) else "FAIL"
    lines = [
        "# Librarian harness responses",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        f"Overall: {overall}",
        "",
    ]

    for result in librarian_live:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"## {result.name} ({status})")
        lines.append("")

        wrote_turn = False
        for turn in result.turns:
            if not turn.response_text.strip():
                continue
            wrote_turn = True
            lines.append(f"### Turn {turn.index}")
            lines.append("")
            if turn.user_send:
                lines.extend(_blockquote_lines(turn.user_send))
                lines.append("")
            lines.append(turn.response_text)
            lines.append("")

        if not wrote_turn:
            lines.append("_No agent responses in this scenario._")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_response_markdown(
    results: list[ScenarioResult],
    report_dir: Path,
    *,
    stamp: str,
) -> Path | None:
    body = format_response_markdown(results)
    if body is None:
        return None
    report_dir.mkdir(parents=True, exist_ok=True)
    out = report_dir / f"{stamp}-report.md"
    out.write_text(body, encoding="utf-8")
    return out


@dataclass(frozen=True)
class HarnessReportPaths:
    json: Path
    markdown: Path | None = None
