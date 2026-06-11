"""In-memory Janitor workflow state per Telegram user."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class JanitorPhase(str, Enum):
    IDLE = "idle"
    AWAIT_EPISODE = "await_episode"
    AWAIT_NOTES = "await_notes"
    PREVIEW = "preview"
    CONFIRM_OVERWRITE = "confirm_overwrite"
    REVIEW_DRAFT = "review_draft"
    AWAIT_PUSH = "await_push"


@dataclass
class JanitorSession:
    phase: JanitorPhase = JanitorPhase.IDLE
    episode_id: str | None = None
    raw_paste: str | None = None
    cleaned_body: str | None = None
    last_error: str | None = None


class JanitorStore:
    def __init__(self) -> None:
        self._sessions: dict[int, JanitorSession] = {}

    def get(self, user_id: int) -> JanitorSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = JanitorSession()
        return self._sessions[user_id]

    def reset(self, user_id: int) -> None:
        self._sessions[user_id] = JanitorSession()

    def is_active(self, user_id: int) -> bool:
        return self.get(user_id).phase != JanitorPhase.IDLE
