import json
from unittest.mock import MagicMock, patch

import attribute_posts_llm as llm


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


@patch("openai.OpenAI")
def test_call_openai_parses_response(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "episode_number": 88,
                            "confidence": 0.85,
                            "reason": "buffett letters",
                        }
                    )
                )
            )
        ]
    )
    result = llm.call_openai(
        text="Warren Buffett shareholder letters ep 88",
        catalog_context="88\t2020-01-01\t#88 Buffett",
        model="gpt-4o-mini",
        api_key="test-key",
    )
    assert result["episode_number"] == 88
    assert result["confidence"] == 0.85
