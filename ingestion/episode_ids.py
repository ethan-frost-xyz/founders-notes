"""Episode id formatting and parsing."""

from __future__ import annotations

import re

EPISODE_NUMBER_WIDTH = 4  # ep-0001 … ep-9999
NUMBERED_EPISODE_ID_RE = re.compile(r"^ep-(\d+)$")


def format_episode_id(episode_number: int) -> str:
    return f"ep-{episode_number:0{EPISODE_NUMBER_WIDTH}d}"


def parse_numbered_episode_id(episode_id: str) -> int | None:
    """Parse ep-1 (legacy) or ep-0001 (canonical) to episode number."""
    m = NUMBERED_EPISODE_ID_RE.match(episode_id)
    return int(m.group(1)) if m else None


def legacy_make_id(episode_number: int) -> str:
    """Unpadded id used before layout migration (ep-1, ep-418)."""
    return f"ep-{episode_number}"


def make_id(episode_number: int | None, slug: str) -> str:
    if episode_number is not None:
        return format_episode_id(episode_number)
    return f"ep-special-{slug}"
