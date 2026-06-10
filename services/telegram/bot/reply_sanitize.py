"""Strip reasoning / DSML markup from user-visible Librarian replies."""

from __future__ import annotations

import re

_REASONING_BLOCK_RE = re.compile(
    r"<think(?:ing)?>.*?</think(?:ing)?>",
    re.IGNORECASE | re.DOTALL,
)
_REDACTED_OPEN = "<" + "redacted_reasoning" + ">"
_REDACTED_CLOSE = "</" + "redacted_reasoning" + ">"
_REDACTED_REASONING_RE = re.compile(
    re.escape(_REDACTED_OPEN) + r".*?" + re.escape(_REDACTED_CLOSE),
    re.IGNORECASE | re.DOTALL,
)
_DSML_BLOCK_RE = re.compile(r"<DSML[^>]*>.*?</DSML>", re.IGNORECASE | re.DOTALL)
_DSML_TAG_RE = re.compile(r"</?DSML[^>]*>", re.IGNORECASE)


def sanitize_librarian_reply(text: str) -> str:
    """Remove model-internal markup; return stripped prose (may be empty)."""
    if not text:
        return ""
    cleaned = text
    for pattern in (
        _REDACTED_REASONING_RE,
        _REASONING_BLOCK_RE,
        _DSML_BLOCK_RE,
        _DSML_TAG_RE,
    ):
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()
