"""Assemble the Telegram Librarian system prompt from AGENTS.md (persona-only)."""

from __future__ import annotations

import json
from pathlib import Path

from config import AgentConfig

_LEGACY_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "vault_agent.md"
)
_CURSOR_SECTION_MARKER = "## Cursor Cloud"


def load_librarian_persona(vault_root: Path) -> str:
    """Load AGENTS.md persona, stripping Cursor-only ops instructions."""
    path = vault_root / "AGENTS.md"
    if not path.is_file():
        path = _LEGACY_PROMPT_PATH
    text = path.read_text(encoding="utf-8")
    if _CURSOR_SECTION_MARKER in text:
        text = text[: text.index(_CURSOR_SECTION_MARKER)].rstrip()
    return text.strip()


def build_system_message(config: AgentConfig) -> str:
    from index_status import index_metadata

    base = load_librarian_persona(config.vault_root)
    meta = index_metadata(config.vault_root)
    meta_line = json.dumps(meta, separators=(",", ":"))
    return f"{base}\n\n---\nRuntime: index_metadata={meta_line}"
