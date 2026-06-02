"""Curated OpenRouter slugs for Telegram tap-to-pick model UI."""

from __future__ import annotations

# (short button label, full slug)
MODEL_PRESETS: dict[str, list[tuple[str, str]]] = {
    "librarian": [
        ("mimo-v2.5-pro", "xiaomi/mimo-v2.5-pro"),
        ("claude-sonnet-4.6", "anthropic/claude-sonnet-4.6"),
        ("gemini-3.5-flash", "google/gemini-3.5-flash"),
        ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
    ],
    "retrieval": [
        ("gpt-oss-20b Groq", "openai/gpt-oss-20b::Groq"),
        ("llama-3.1-8b", "meta-llama/llama-3.1-8b-instruct"),
        ("gemini-3.5-flash", "google/gemini-3.5-flash"),
    ],
    "janitor": [
        ("gpt-oss-20b Groq", "openai/gpt-oss-20b::Groq"),
        ("llama-3.1-8b", "meta-llama/llama-3.1-8b-instruct"),
        ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
    ],
    "expand": [
        ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
        ("claude-sonnet-4.6", "anthropic/claude-sonnet-4.6"),
        ("gpt-5.4-mini", "openai/gpt-5.4-mini"),
    ],
    "embed": [
        ("qwen3-embed-8b", "qwen/qwen3-embedding-8b"),
        ("text-embedding-3-small", "openai/text-embedding-3-small"),
    ],
}

ROLE_LABELS: dict[str, str] = {
    "librarian": "Librarian Q&A",
    "retrieval": "Librarian expand + rerank",
    "janitor": "Janitor clean",
    "expand": "Expand datapoints",
    "embed": "Search embeddings",
}
