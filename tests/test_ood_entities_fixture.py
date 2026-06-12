"""Verify OOD fixture entities stay absent from catalog/episodes.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "dev" / "scenarios" / "librarian" / "fixtures" / "ood_entities.yaml"
CATALOG = REPO / "catalog" / "episodes.jsonl"


def _catalog_text() -> str:
    return CATALOG.read_text(encoding="utf-8").lower()


def _load_fixture_entities() -> list[dict]:
    import yaml

    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    entities = data.get("entities") or []
    assert isinstance(entities, list)
    return entities


@pytest.mark.parametrize(
    "entity",
    _load_fixture_entities(),
    ids=lambda e: str(e.get("name", "entity")),
)
def test_ood_entity_tokens_absent_from_catalog(entity: dict) -> None:
    tokens = entity.get("verify_absent") or []
    if not tokens:
        pytest.skip("no verify_absent tokens")
    catalog = _catalog_text()
    for token in tokens:
        needle = str(token).lower()
        assert needle not in catalog, (
            f"OOD fixture {entity.get('name')!r}: {token!r} found in catalog — "
            "update ood_decline.yaml or remove from fixture"
        )


def test_ood_fixture_has_entities() -> None:
    entities = _load_fixture_entities()
    assert len(entities) >= 2


def test_catalog_jsonl_parseable() -> None:
    lines = [ln for ln in CATALOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for line in lines[:5]:
        json.loads(line)
