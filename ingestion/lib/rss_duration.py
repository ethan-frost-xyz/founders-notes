"""Parse podcast RSS itunes:duration values."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ITUNES_DURATION_TAG = f"{{{ITUNES_NS}}}duration"

_HMS_RE = re.compile(r"^(\d+):(\d{2})(?::(\d{2}))?$")


def parse_itunes_duration(raw: str | None) -> int | None:
    """Return duration in seconds, or None if missing/unparseable."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    m = _HMS_RE.match(text)
    if not m:
        return None
    h_or_m, mm, ss = m.group(1), m.group(2), m.group(3)
    if ss is not None:
        return int(h_or_m) * 3600 + int(mm) * 60 + int(ss)
    return int(h_or_m) * 60 + int(mm)


def duration_seconds_from_rss_item(item: ET.Element) -> int | None:
    el = item.find(ITUNES_DURATION_TAG)
    if el is None or not el.text:
        return None
    return parse_itunes_duration(el.text)
