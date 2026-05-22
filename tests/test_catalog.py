import pytest

from catalog import resolve_catalog_row


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


def test_resolve_catalog_row_missing():
    with pytest.raises(SystemExit):
        resolve_catalog_row([], "ep-9999")
