"""Curated OpenRouter slugs for Telegram tap-to-pick model UI."""

from __future__ import annotations

# (short button label, full slug)
MODEL_PRESETS: dict[str, list[tuple[str, str]]] = {
    "librarian": [
        ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
        ("claude-sonnet-4", "anthropic/claude-sonnet-4"),
        ("gpt-4.1-mini", "openai/gpt-4.1-mini"),
        ("gemini-2.5-flash", "google/gemini-2.5-flash-preview"),
    ],
    "janitor": [
        ("gpt-oss-20b Groq", "openai/gpt-oss-20b::Groq"),
        ("llama-3.1-8b", "groq/llama-3.1-8b-instant"),
        ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
        ("gpt-4.1-mini", "openai/gpt-4.1-mini"),
    ],
    "expand": [
        ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
        ("claude-sonnet-4", "anthropic/claude-sonnet-4"),
        ("gpt-4.1-mini", "openai/gpt-4.1-mini"),
    ],
    "embed": [
        ("qwen3-embed-8b", "qwen/qwen3-embedding-8b"),
        ("text-embedding-3-small", "openai/text-embedding-3-small"),
    ],
}

ROLE_LABELS: dict[str, str] = {
    "librarian": "Librarian Q&A",
    "janitor": "Janitor clean",
    "expand": "Expand datapoints",
    "embed": "Search embeddings",
}
