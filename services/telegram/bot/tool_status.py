"""User-visible status labels while the Librarian runs vault tools."""

from __future__ import annotations

TOOL_STATUS_LABELS: dict[str, str] = {
    "search_vault_parent": "Searching notes…",
    "search_transcript": "Searching transcripts…",
    "load_episode": "Loading episode…",
    "list_episode_ids": "Looking up episode…",
    "web_search": "Searching the web…",
}


def tool_status_label(tool_name: str) -> str:
    return TOOL_STATUS_LABELS.get(tool_name, "Searching vault…")
