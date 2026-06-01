"""User-visible status labels while the Librarian runs vault tools."""

from __future__ import annotations

TOOL_STATUS_LABELS: dict[str, str] = {
    "search_vault_parent": "Searching notes…",
    "search_transcript": "Searching transcripts…",
    "load_episode": "Loading episode…",
    "list_episode_ids": "Looking up episode…",
    "web_search": "Searching the web…",
    "retrieval": "Searching vault…",
    "synthesis": "Composing answer…",
}

RETRIEVAL_STATUS_LABELS: dict[str, str] = {
    "Expanding query…": "Expanding query…",
    "Searching vault…": "Searching vault…",
    "Ranking results…": "Ranking results…",
}


def tool_status_label(tool_name: str) -> str:
    return TOOL_STATUS_LABELS.get(tool_name, "Searching vault…")


def retrieval_status_label(status: str) -> str:
    return RETRIEVAL_STATUS_LABELS.get(status, status)
