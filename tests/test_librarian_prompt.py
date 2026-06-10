"""Tests for Telegram Librarian prompt assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from config import AgentConfig  # noqa: E402
from librarian_prompt import build_system_message, load_librarian_persona  # noqa: E402


def test_load_librarian_persona_strips_cursor_section():
    persona = load_librarian_persona(REPO)
    assert "Cursor Cloud" not in persona
    assert "mock_telegram_cli" not in persona
    assert "Retrieve before you cite" in persona


def test_build_system_message_includes_index_metadata(agent_config: AgentConfig):
    msg = build_system_message(agent_config)
    assert "index_metadata=" in msg
    assert "mock_telegram_cli" not in msg
