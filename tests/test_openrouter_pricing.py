"""Tests for OpenRouter catalog pricing (no live network in unit tests)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import paths
from expand_llm import ExpandEstimate, print_expand_dry_run_summary
from openrouter_pricing import (
    COMPLETION_TOKENS_PER_BULLET,
    ModelRates,
    _cache_is_fresh,
    estimate_cost_usd,
    find_model_entry,
    format_usd_per_million,
    get_models_catalog,
    load_catalog_from_cache,
    pick_pricing_tier,
    rates_from_model_entry,
    resolve_model_rates,
    write_catalog_cache,
)

SAMPLE_CATALOG = [
    {
        "id": "test/simple",
        "canonical_slug": "test/simple-v1",
        "name": "Test Simple",
        "pricing": {
            "prompt": "0.000001",
            "completion": "0.000002",
            "request": "0",
        },
    },
    {
        "id": "test/tiered",
        "canonical_slug": "test/tiered-v1",
        "name": "Test Tiered",
        "pricing": [
            {
                "prompt": "0.000001",
                "completion": "0.000002",
                "request": "0",
            },
            {
                "prompt": "0.000004",
                "completion": "0.000008",
                "min_context": 1000,
            },
        ],
    },
]


def test_pick_pricing_tier_base():
    tier = pick_pricing_tier(SAMPLE_CATALOG[1]["pricing"], 500)
    assert tier["prompt"] == "0.000001"


def test_pick_pricing_tier_long_context():
    tier = pick_pricing_tier(SAMPLE_CATALOG[1]["pricing"], 1500)
    assert tier["prompt"] == "0.000004"


def test_rates_from_model_entry():
    rates = rates_from_model_entry(SAMPLE_CATALOG[0])
    assert rates.prompt_usd_per_token == 0.000001
    assert rates.completion_usd_per_token == 0.000002
    assert rates.prompt_usd_per_million == 1.0


def test_find_model_entry_by_id_and_slug():
    assert find_model_entry(SAMPLE_CATALOG, "test/simple") is not None
    assert find_model_entry(SAMPLE_CATALOG, "test/simple-v1") is not None
    assert find_model_entry(SAMPLE_CATALOG, "missing/model") is None


def test_estimate_cost_usd():
    rates = rates_from_model_entry(SAMPLE_CATALOG[0])
    costs = estimate_cost_usd(
        rates, input_tokens=1_000_000, n_calls=10, total_bullets=4
    )
    assert costs.input_usd == 1.0
    assert costs.output_usd == 4 * COMPLETION_TOKENS_PER_BULLET * 0.000002
    assert costs.request_usd == 0.0
    assert costs.total_usd == costs.input_usd + costs.output_usd


def test_cache_freshness_and_load(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    import openrouter_pricing as op

    monkeypatch.setattr(op, "CACHE_PATH", tmp_path / "catalog" / "openrouter-models-cache.json")

    fresh = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data": SAMPLE_CATALOG,
    }
    assert _cache_is_fresh(fresh)

    stale = {
        "fetched_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
        "data": SAMPLE_CATALOG,
    }
    assert not _cache_is_fresh(stale)

    write_catalog_cache(SAMPLE_CATALOG)
    loaded = load_catalog_from_cache()
    assert loaded is not None
    assert len(loaded) == 2


@patch("openrouter_pricing.fetch_models_catalog")
def test_get_models_catalog_uses_cache(mock_fetch, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    import openrouter_pricing as op

    monkeypatch.setattr(op, "CACHE_PATH", tmp_path / "catalog" / "openrouter-models-cache.json")
    write_catalog_cache(SAMPLE_CATALOG)

    data = get_models_catalog()
    mock_fetch.assert_not_called()
    assert len(data) == 2

    mock_fetch.return_value = SAMPLE_CATALOG
    data2 = get_models_catalog(force_refresh=True)
    mock_fetch.assert_called_once()
    assert len(data2) == 2


@patch("openrouter_pricing.get_models_catalog")
def test_resolve_model_rates(mock_catalog):
    mock_catalog.return_value = SAMPLE_CATALOG
    rates = resolve_model_rates("test/simple", input_tokens=100)
    assert rates.model_id == "test/simple"
    assert rates.prompt_usd_per_token == 0.000001


@patch("expand_llm.resolve_model_rates")
def test_print_expand_dry_run_summary_shows_cost(mock_resolve, tmp_path: Path, capsys):
    mock_resolve.return_value = ModelRates(
        model_id="test/simple",
        name="Test Simple",
        prompt_usd_per_token=0.000001,
        completion_usd_per_token=0.000002,
        request_usd_per_call=0.0,
    )
    prompt = tmp_path / "p.md"
    prompt.write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{n}\n{t}\n", encoding="utf-8")
    estimates = [
        ExpandEstimate(
            episode_id="ep-0001",
            n_bullets=2,
            notes_chars=100,
            transcript_chars=1000,
            input_chars=2000,
        )
    ]
    print_expand_dry_run_summary(
        estimates,
        title="Test dry-run",
        prompt_path=prompt,
        model="test/simple",
    )
    out = capsys.readouterr().out
    assert "~input cost:" in out
    assert "~total (est.):" in out
    assert "test/simple" in out
    assert format_usd_per_million(0.000001) in out


@patch("expand_llm.resolve_model_rates")
def test_print_expand_dry_run_summary_unset_model(mock_resolve, tmp_path: Path, capsys):
    prompt = tmp_path / "p.md"
    prompt.write_text("<<<SYSTEM>>>\nx\n<<<USER>>>\n{n}\n{t}\n", encoding="utf-8")
    estimates = [
        ExpandEstimate(
            episode_id="ep-0001",
            n_bullets=1,
            notes_chars=10,
            transcript_chars=10,
            input_chars=100,
        )
    ]
    print_expand_dry_run_summary(
        estimates,
        title="Test",
        prompt_path=prompt,
        model="(unset)",
    )
    mock_resolve.assert_not_called()
    assert "OPENROUTER_MODEL" in capsys.readouterr().out
