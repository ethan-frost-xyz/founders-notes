"""Validation and parsing for expanded datapoint drafts."""

from __future__ import annotations

import re
from pathlib import Path

from expanded_timestamp_lint import lint_expanded_body
from markdown_io import TIMESTAMP_BULLET_RE, read_markdown_body

_FENCE_RE = re.compile(
    r"^\s*```(?:markdown|md)?\s*\r?\n(.*?)\r?\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def parse_expanded_body(raw: str) -> str:
    """Strip optional markdown fence and preamble; return body starting at ## Expanded datapoints."""
    text = raw.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    marker = "## Expanded datapoints"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"Model output missing {marker!r}")
    return text[idx:].strip()


def count_datapoint_headings(body: str) -> int:
    return len(re.findall(r"^###\s+.+$", body, re.MULTILINE))


def count_datapoint_headings_in_partial(text: str) -> int:
    """Count completed `###` datapoint headings in a partial stream buffer."""
    return count_datapoint_headings(text)


def _block_has_field(block: str, labels: tuple[str, ...]) -> bool:
    """True if block contains any label (plain or **Label:** markdown)."""
    lower = block.lower()
    for label in labels:
        if label.lower() in lower:
            return True
        bold = f"**{label}**"
        if bold.lower() in lower:
            return True
    return False


def validate_expanded_draft(
    notes_path: Path,
    expanded_body: str,
) -> tuple[list[str], list[str]]:
    """
    Return (errors, warnings). Errors block promotion; warnings are advisory.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if "## Expanded datapoints" not in expanded_body:
        errors.append("missing ## Expanded datapoints section")
        return errors, warnings

    n_sections = count_datapoint_headings(expanded_body)
    if n_sections == 0:
        errors.append("no ### datapoint headings found")

    notes_body = read_markdown_body(notes_path)
    n_bullets = len(TIMESTAMP_BULLET_RE.findall(notes_body))
    if n_bullets > 0 and n_sections < n_bullets:
        errors.append(
            f"fewer expanded sections ({n_sections}) than note bullets ({n_bullets})"
        )
    if n_sections > n_bullets and n_bullets > 0:
        warnings.append(
            f"more ### sections ({n_sections}) than note bullets ({n_bullets})"
        )

    for i, block in enumerate(re.split(r"^###\s+", expanded_body, flags=re.MULTILINE)):
        if i == 0:
            continue
        if not _block_has_field(block, ("Context:",)):
            warnings.append(f"block after heading #{i} may be missing Context:")
        if not _block_has_field(block, ("Quote:",)):
            warnings.append(f"block after heading #{i} may be missing Quote:")
        if not _block_has_field(
            block, ("Key takeaway:", "Takeaway:")
        ):
            warnings.append(
                f"block after heading #{i} may be missing Key takeaway: or Takeaway:"
            )

    for msg in lint_expanded_body(expanded_body):
        warnings.append(f"timestamp meta: {msg}")

    return errors, warnings
