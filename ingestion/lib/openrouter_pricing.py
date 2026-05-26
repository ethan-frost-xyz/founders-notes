"""Fetch OpenRouter model catalog pricing for dry-run cost estimates."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

import paths

MODELS_URL = "https://openrouter.ai/api/v1/models"
CACHE_PATH = paths.ROOT / "catalog" / "openrouter-models-cache.json"
CACHE_TTL = timedelta(hours=24)
REQUEST_TIMEOUT_SEC = 15

# Rough completion size per expanded bullet (Context + Quote + Key takeaway).
COMPLETION_TOKENS_PER_BULLET = 500


@dataclass(frozen=True)
class ModelRates:
    model_id: str
    name: str
    prompt_usd_per_token: float
    completion_usd_per_token: float
    request_usd_per_call: float

    @property
    def prompt_usd_per_million(self) -> float:
        return self.prompt_usd_per_token * 1_000_000

    @property
    def completion_usd_per_million(self) -> float:
        return self.completion_usd_per_token * 1_000_000


@dataclass(frozen=True)
class CostEstimate:
    input_usd: float
    output_usd: float
    request_usd: float

    @property
    def total_usd(self) -> float:
        return self.input_usd + self.output_usd + self.request_usd


def _parse_usd(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def pick_pricing_tier(pricing: Any, input_tokens: int) -> dict[str, Any]:
    """Select pricing tier; base tier is index 0, higher tiers use min_context."""
    if isinstance(pricing, dict):
        return pricing
    if isinstance(pricing, list) and pricing:
        tier = pricing[0]
        for candidate in pricing[1:]:
            if not isinstance(candidate, dict):
                continue
            min_ctx = int(candidate.get("min_context") or 0)
            if input_tokens >= min_ctx:
                tier = candidate
        return tier if isinstance(tier, dict) else {}
    return {}


def rates_from_model_entry(entry: dict[str, Any], *, input_tokens: int = 0) -> ModelRates:
    pricing = pick_pricing_tier(entry.get("pricing"), input_tokens)
    return ModelRates(
        model_id=str(entry.get("id", "")),
        name=str(entry.get("name", entry.get("id", ""))),
        prompt_usd_per_token=_parse_usd(pricing.get("prompt")),
        completion_usd_per_token=_parse_usd(pricing.get("completion")),
        request_usd_per_call=_parse_usd(pricing.get("request")),
    )


def _cache_is_fresh(cache: dict[str, Any]) -> bool:
    fetched_at = cache.get("fetched_at")
    if not fetched_at:
        return False
    try:
        ts = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - ts < CACHE_TTL


def fetch_models_catalog(*, api_key: str | None = None) -> list[dict[str, Any]]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.get(MODELS_URL, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("OpenRouter models response missing data[]")
    return data


def load_catalog_from_cache() -> list[dict[str, Any]] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not _cache_is_fresh(cache):
        return None
    data = cache.get("data")
    return data if isinstance(data, list) else None


def write_catalog_cache(data: list[dict[str, Any]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "data": data},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def get_models_catalog(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    if not force_refresh:
        cached = load_catalog_from_cache()
        if cached is not None:
            return cached
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip() or None
    data = fetch_models_catalog(api_key=api_key)
    write_catalog_cache(data)
    return data


def find_model_entry(catalog: list[dict[str, Any]], model_id: str) -> dict[str, Any] | None:
    model_id = model_id.strip()
    if not model_id:
        return None
    for entry in catalog:
        if entry.get("id") == model_id:
            return entry
    for entry in catalog:
        if entry.get("canonical_slug") == model_id:
            return entry
    return None


def resolve_model_rates(model_id: str, *, input_tokens: int = 0) -> ModelRates:
    catalog = get_models_catalog()
    entry = find_model_entry(catalog, model_id)
    if entry is None:
        raise LookupError(f"Model not found in OpenRouter catalog: {model_id}")
    return rates_from_model_entry(entry, input_tokens=input_tokens)


def estimate_cost_usd(
    rates: ModelRates,
    *,
    input_tokens: int,
    n_calls: int,
    total_bullets: int,
) -> CostEstimate:
    input_usd = input_tokens * rates.prompt_usd_per_token
    output_tokens = total_bullets * COMPLETION_TOKENS_PER_BULLET
    output_usd = output_tokens * rates.completion_usd_per_token
    request_usd = n_calls * rates.request_usd_per_call
    return CostEstimate(
        input_usd=input_usd,
        output_usd=output_usd,
        request_usd=request_usd,
    )


def format_usd_per_million(usd_per_token: float) -> str:
    per_m = usd_per_token * 1_000_000
    if per_m == 0:
        return "$0"
    if per_m >= 1:
        return f"${per_m:.2f}/M"
    if per_m >= 0.01:
        return f"${per_m:.3f}/M"
    return f"${per_m:.4f}/M"


def model_id_for_pricing(model: str) -> str | None:
    """Return OpenRouter model id if configured; None if unset/placeholder."""
    m = model.strip()
    if not m or m == "(unset)":
        return None
    return m
