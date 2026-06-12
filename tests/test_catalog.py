import json
import os
import time

import pytest

from catalog import clear_jsonl_cache, load_jsonl, lookup_catalog_row, resolve_catalog_row


def test_resolve_catalog_row_by_id():
    rows = [
        {"id": "ep-0200", "episode_number": 200, "slug": "200-test", "title": "Test"},
    ]
    assert resolve_catalog_row(rows, "ep-0200")["episode_number"] == 200


def test_resolve_catalog_row_by_legacy_number():
    rows = [
        {"id": "ep-0200", "episode_number": 200, "slug": "200-test", "title": "Test"},
    ]
    assert resolve_catalog_row(rows, "ep-200")["id"] == "ep-0200"


def test_lookup_catalog_row_missing():
    assert lookup_catalog_row([], "ep-9999") is None


def test_resolve_catalog_row_missing():
    with pytest.raises(SystemExit):
        resolve_catalog_row([], "ep-9999")


def test_load_jsonl_refreshes_when_file_changes_on_disk(tmp_path):
    path = tmp_path / "episodes.jsonl"
    path.write_text(
        json.dumps({"id": "ep-0001", "episode_number": 1, "title": "First"}) + "\n",
        encoding="utf-8",
    )
    assert load_jsonl(path)[0]["title"] == "First"

    path.write_text(
        json.dumps({"id": "ep-0001", "episode_number": 1, "title": "Updated"}) + "\n",
        encoding="utf-8",
    )
    # Same-second writes can share mtime; bump so the cache key changes.
    os.utime(path, (time.time() + 1, time.time() + 1))
    assert load_jsonl(path)[0]["title"] == "Updated"
    clear_jsonl_cache()
