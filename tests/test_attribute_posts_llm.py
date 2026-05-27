import json
from unittest.mock import patch

import attribute_posts_llm as llm
from openrouter_client import OpenRouterCompletion


def test_parse_llm_attribution_response_plain_json():
    raw = '{"episode_number": 131, "confidence": 0.9, "reason": "mentions ep 131"}'
    data = llm.parse_llm_attribution_response(raw)
    assert data["episode_number"] == 131
    assert data["confidence"] == 0.9


def test_parse_llm_attribution_response_fenced_json():
    raw = '```json\n{"episode_number": null, "confidence": 0.2, "reason": "off topic"}\n```'
    data = llm.parse_llm_attribution_response(raw)
    assert data["episode_number"] is None


def test_build_catalog_context_includes_numbered_rows():
    rows = [
        {"episode_number": 2, "title": "#2 Foo", "published_at": "2020-01-01"},
        {"episode_number": 1, "title": "#1 Bar", "published_at": "2019-01-01"},
        {"episode_number": None, "title": "Special", "published_at": None},
    ]
    ctx = llm.build_catalog_context(rows)
    assert "1\t2019-01-01\t#1 Bar" in ctx
    assert "2\t2020-01-01\t#2 Foo" in ctx
    assert "Special" not in ctx


def test_resolve_attribution_model_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ATTRIBUTION_MODEL", "anthropic/claude-3-haiku")
    assert llm.resolve_attribution_model("openai/gpt-4o-mini") == "openai/gpt-4o-mini"


def test_resolve_attribution_model_env_fallback(monkeypatch):
    monkeypatch.delenv("OPENROUTER_ATTRIBUTION_MODEL", raising=False)
    assert llm.resolve_attribution_model(None) == llm.DEFAULT_ATTRIBUTION_MODEL


@patch("attribute_posts_llm.call_openrouter")
def test_call_attribution_llm_parses_response(mock_call_openrouter):
    mock_call_openrouter.return_value = OpenRouterCompletion(
        content=json.dumps(
            {
                "episode_number": 88,
                "confidence": 0.85,
                "reason": "buffett letters",
            }
        ),
        response_id="gen-1",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_usd=0.001,
        duration_ms=100,
    )
    result = llm.call_attribution_llm(
        text="Warren Buffett shareholder letters ep 88",
        catalog_context="88\t2020-01-01\t#88 Buffett",
        model="openai/gpt-4o-mini",
        api_key="test-key",
    )
    assert result["episode_number"] == 88
    assert result["confidence"] == 0.85
    mock_call_openrouter.assert_called_once()
    _, kwargs = mock_call_openrouter.call_args
    assert kwargs["response_format"] == {"type": "json_object"}
