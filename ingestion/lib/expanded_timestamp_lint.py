"""Detect timestamp-meta noise in expanded drafts (not legitimate content-support warnings)."""

from __future__ import annotations

import re

# Substrings that indicate timestamp availability / verification meta (case-insensitive).
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "lacks timestamps",
    "lack timestamps",
    "transcript lacks a timestamp",
    "transcript lacks time codes",
    "transcript lacks precise markers",
    "transcript does not have timestamps",
    "transcript does not contain its own timestamps",
    "un-timestamped block",
    "timestamp is not present in the provided transcript",
    "timestamp not provided in the transcript",
    "timestamp not provided in the raw note",
    "timestamp not provided;",
    "no timestamp is provided in the raw note",
    "no timestamp is given",
    "no timestamp is provided",
    "no timestamp in the raw note",
    "no timestamp was provided in the raw note",
    "no timestamp is recorded in the raw note",
    "no timestamp is present in the raw note",
    "the raw note has no timestamp",
    "does not include explicit timestamps",
    "does not include in-line timecodes",
    "the raw note lacks a timestamp",
    "the raw note had no timestamp",
    "timestamp for this bullet was not provided",
    "the raw note omits a timestamp",
    "timestamp is missing",
    "timestamp is also missing",
    "timestamp is approximate",
    "approximate as the transcript lacks",
    "from the raw notes; the transcript",
    "not verified against transcript timestamp",
    "transcript around this timestamp",
)

# Regex for Quote-line parentheticals that are not bare (MM:SS) or (H:MM:SS).
NOISY_QUOTE_PAREN_RE = re.compile(
    r"\("
    r"(?!(\d{1,2}:\d{2}(?::\d{2})?)\s*\))"  # not only MM:SS
    r"[^)]*"
    r"(?:timestamp|transcript|raw note|raw bullet|not provided|not verified|lacks|approximate)",
    re.IGNORECASE,
)

# Clauses/sentences to strip from Context / Key takeaway (order matters for overlaps).
STRIP_CLAUSE_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\s*No timestamp is provided in the raw note\.?",
        r"\s*No timestamp is given\.?",
        r"\s*No timestamp is provided\.?",
        r"\s*No timestamp is given for this note\.?\s*",
        r"\s*The timestamp for this bullet was not provided in the raw note\.?",
        r"\s*The timestamp \d{1,2}:\d{2} is noted in the raw bullet but cannot be verified against the transcript, which lacks timestamps\.?",
        r"\s*The timestamp is given as \d{1,2}:\d{2}, though the transcript lacks precise markers, so the passage is placed approximately there\.?",
        r"\s*The timestamp is noted as \d{1,2}:\d{2}, though the transcript lacks time codes; the quoted passage appears[^.]*\.",
        r"\s*; the timestamp is missing, but this is the opening anecdote\.?",
        r"\s*; no timestamp is available, but the story is part of the founding history\.?",
        r"\s*The raw note lacks a timestamp\.?\s*",
        r"\s*This raw note lacks a timestamp\.?\s*",
        r"\s*The raw note had no timestamp\.?\s*",
        r"\s*The timestamp is approximate, taken from the raw note and positioned late in the episode\.?",
        r"\s*The timestamp is from the raw notes; the transcript does not contain its own timestamps\.?",
        r"\s*The timestamp aligns with this section\.?",
        r"\s*The timestamp for this specific concept is not explicitly stated in the transcript\.?",
        r"\s*but the timestamp aligns with this section\.?",
        r"\s*The timestamp \d{1,2}:\d{2} is not present in the provided transcript[^.]*\.",
        r"\s*The timestamp \d{1,2}:\d{2} is not present in the provided transcript, which is a single, un-timestamped block of text\.?",
        r"\s*The raw note omits a timestamp;[^.]*\.",
        r"\s*The transcript lacks a timestamp for this point\.?",
        r"\s*The timestamp is missing, so the quote is drawn[^.]*\.",
        r"\s*Timestamp not provided in the raw note;[^.]*\.",
        r"\s*Timestamp not provided;[^.]*\.",
        r"\s*Timestamp is also missing\.?",
        r"\s*The raw note's timestamp is approximate\.?",
        r"\s*No timestamp was provided in the raw note;[^.]*\.",
        r"\s*No timestamp is recorded in the raw note;[^.]*\.",
        r"\s*No timestamp in the raw note, but this is from[^.]*\.",
        r"\s*This raw note appears at the same timestamp as the previous bullet, but[^.]*\.",
        r",\s*but both instances appear in the transcript\.?",  # artifact from bad strip
        r"\s*The raw note's timestamp is approximate\.?",
        r"\s*The raw note's timestamp is approximate,[^.]*\.",
        r"\s*No timestamp was provided in the raw note;[^.]*\.",
        r"\s*No timestamp was provided in the raw note\.?",
        r"\s*The timestamp is approximate[^.]*\.",
        r"\s*The note's timestamp is approximate[^.]*\.",
        r"\s*The raw note['\u2019]s timestamp is approximate[^.]*\.",
        r"\s*The raw note['\u2019]s timestamp is approximate\.?",
        r"\s*The note['\u2019]s timestamp is approximate[^.]*\.?",
        r"\s*No timestamp is present in the raw note\.?",
        r"\s*The raw note has no timestamp, but[^.]*\.",
        r"; the transcript around this timestamp[^.]*\.",
    )
)

# Quote suffix: extract MM:SS from noisy Timestamp (...) parentheticals.
NOISY_TIMESTAMP_PAREN_RE = re.compile(
    r'\s*\((?:Timestamp[^)]*?)?(\d{1,2}:\d{2}(?::\d{2})?)[^)]*\)\s*$',
    re.IGNORECASE,
)
BARE_TIMESTAMP_PAREN_RE = re.compile(r"\s*\((\d{1,2}:\d{2}(?::\d{2})?)\)\s*$")
STRIP_META_PAREN_RE = re.compile(
    r"\s*\([^)]*(?:timestamp|transcript lacks|not provided in transcript|not verified|"
    r"no timestamp in transcript|inferred from context)[^)]*\)\s*$",
    re.IGNORECASE,
)


def contains_forbidden_timestamp_meta(text: str) -> list[str]:
    """Return forbidden substring hits (empty if clean)."""
    lower = text.lower()
    return [s for s in FORBIDDEN_SUBSTRINGS if s in lower]


def has_noisy_quote_paren(text: str) -> bool:
    for line in text.splitlines():
        if line.startswith("Quote:"):
            tail = line[len("Quote:") :].strip()
            if NOISY_QUOTE_PAREN_RE.search(tail):
                return True
    return False


def lint_expanded_body(body: str) -> list[str]:
    """Warnings for timestamp-meta noise in expanded datapoint body."""
    warnings: list[str] = []
    for hit in contains_forbidden_timestamp_meta(body):
        warnings.append(f"timestamp meta phrase: {hit!r}")
    if has_noisy_quote_paren(body):
        warnings.append("Quote line has non-(MM:SS) timestamp parenthetical")
    return warnings


def _clean_quote_line(line: str, heading_ts: str | None) -> str:
    if not line.startswith("Quote:"):
        return line
    prefix = "Quote:"
    rest = line[len(prefix) :].strip()
    m = NOISY_TIMESTAMP_PAREN_RE.search(rest)
    if m:
        ts = m.group(1)
        rest = rest[: m.start()].rstrip() + f" ({ts})"
        return f"{prefix} {rest}"
    m2 = STRIP_META_PAREN_RE.search(rest)
    if m2:
        rest = rest[: m2.start()].rstrip()
        if heading_ts and not rest.rstrip().endswith(f"({heading_ts})"):
            rest = rest + f" ({heading_ts})"
        return f"{prefix} {rest}"
    return line


def _heading_timestamp(block: str) -> str | None:
    m = re.match(r"^###\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+—", block, re.MULTILINE)
    return m.group(1) if m else None


def clean_expanded_body(body: str) -> str:
    """Strip timestamp-meta clauses; normalize Quote suffixes to (MM:SS) or none."""
    parts = re.split(r"(?=^###\s)", body, flags=re.MULTILINE)
    out: list[str] = []
    for part in parts:
        if not part.strip():
            out.append(part)
            continue
        ts = _heading_timestamp(part)
        for pat in STRIP_CLAUSE_RES:
            part = pat.sub("", part)
        lines = part.splitlines()
        new_lines: list[str] = []
        for line in lines:
            if line.startswith(("Context:", "Key takeaway:")):
                for pat in STRIP_CLAUSE_RES:
                    line = pat.sub("", line)
            if line.startswith("Quote:"):
                line = _clean_quote_line(line, ts)
            new_lines.append(line)
        out.append("\n".join(new_lines))
    text = "".join(out)
    text = re.sub(r"(## Expanded datapoints)\s*(### )", r"\1\n\n\2", text)
    text = re.sub(r"([.!?\"])(### )", r"\1\n\n\2", text)
    return text
