"""Tests for RSS itunes:duration parsing."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from rss_duration import duration_seconds_from_rss_item, parse_itunes_duration

FIXTURE = Path(__file__).resolve().parent.parent / "ingestion/fixtures/rss-duration-snippet.xml"


def test_parse_itunes_duration_formats():
    assert parse_itunes_duration("3721") == 3721
    assert parse_itunes_duration("1:02:01") == 3721
    assert parse_itunes_duration("45:30") == 2730
    assert parse_itunes_duration("") is None
    assert parse_itunes_duration("bad") is None


def test_duration_seconds_from_rss_item_fixture():
    root = ET.parse(FIXTURE).getroot()
    items = root.findall(".//item")
    assert duration_seconds_from_rss_item(items[0]) == 3721
    assert duration_seconds_from_rss_item(items[1]) == 3721
    assert duration_seconds_from_rss_item(items[2]) == 2730
    assert duration_seconds_from_rss_item(items[3]) is None
