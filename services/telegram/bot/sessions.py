"""In-memory chat sessions with jsonl export/resume."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import BotConfig

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class SessionMessage:
    role: str
    content: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class UserSession:
    messages: list[SessionMessage] = field(default_factory=list)
    slug: str = "session"
    last_export_path: Path | None = None


def _slugify(text: str, *, max_len: int = 40) -> str:
    base = _SLUG_RE.sub("-", text.lower().strip())[:max_len].strip("-")
    return base or "session"


def _utc_filename_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def index_newest_mtime(vault_root: Path) -> float:
    candidates = [
        vault_root / "catalog" / "chunks.jsonl",
        vault_root / "catalog" / "embeddings-manifest.jsonl",
    ]
    mtimes = [p.stat().st_mtime for p in candidates if p.is_file()]
    return max(mtimes) if mtimes else 0.0


def _session_owner_id(path: Path) -> int | None:
    """Read user_id from exported meta line; None if missing or unreadable."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("record") == "meta":
                uid = row.get("user_id")
                return int(uid) if uid is not None else None
            break
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def session_stale_warning(session_path: Path, vault_root: Path) -> str | None:
    if not session_path.is_file():
        return None
    idx_mtime = index_newest_mtime(vault_root)
    if idx_mtime > session_path.stat().st_mtime:
        return (
            "Note: the vault index was rebuilt after this session was saved. "
            "Answers may not reflect the latest notes until you re-ask."
        )
    return None


class SessionStore:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self._by_user: dict[int, UserSession] = {}
        config.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get(self, user_id: int) -> UserSession:
        if user_id not in self._by_user:
            self._by_user[user_id] = UserSession()
        return self._by_user[user_id]

    def clear(self, user_id: int) -> None:
        self._by_user[user_id] = UserSession()

    def history_for_agent(self, user_id: int) -> list[dict[str, str]]:
        session = self.get(user_id)
        return [
            {"role": m.role, "content": m.content}
            for m in session.messages
            if m.role in ("user", "assistant") and m.content
        ]

    def append_turn(
        self,
        user_id: int,
        *,
        user_text: str,
        assistant_text: str,
        tool_trace: list[dict[str, Any]] | None = None,
    ) -> None:
        session = self.get(user_id)
        if not session.slug or session.slug == "session":
            session.slug = _slugify(user_text[:80])
        session.messages.append(SessionMessage(role="user", content=user_text))
        session.messages.append(
            SessionMessage(
                role="assistant",
                content=assistant_text,
                tool_trace=list(tool_trace or []),
            )
        )

    def export_session(self, user_id: int) -> Path | None:
        session = self.get(user_id)
        if not session.messages:
            return None

        filename = f"{_utc_filename_slug()}_{session.slug}.jsonl"
        path = self.config.sessions_dir / filename
        exported_at = datetime.now(timezone.utc).isoformat()
        lines = [
            json.dumps(
                {
                    "record": "meta",
                    "exported_at": exported_at,
                    "user_id": user_id,
                    "slug": session.slug,
                },
                ensure_ascii=False,
            )
        ]
        for msg in session.messages:
            row: dict[str, Any] = {
                "record": "message",
                "role": msg.role,
                "content": msg.content,
            }
            if msg.tool_trace:
                row["tool_trace"] = msg.tool_trace
            lines.append(json.dumps(row, ensure_ascii=False))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        session.last_export_path = path
        return path

    def new_chat(self, user_id: int) -> Path | None:
        path = self.export_session(user_id)
        self.clear(user_id)
        return path

    def load_session_file(self, path: Path, user_id: int) -> str | None:
        if not path.is_file():
            return f"Session file not found: {path.name}"

        messages: list[SessionMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("record") == "message":
                messages.append(
                    SessionMessage(
                        role=row["role"],
                        content=row.get("content", ""),
                        tool_trace=row.get("tool_trace") or [],
                    )
                )

        if not messages:
            return "Session file has no messages."

        slug = path.stem.split("_", 1)[-1] if "_" in path.stem else "session"
        self._by_user[user_id] = UserSession(messages=messages, slug=slug, last_export_path=path)
        return session_stale_warning(path, self.config.agent.vault_root)

    def _sessions_for_user(self, user_id: int) -> list[Path]:
        files = [
            p
            for p in self.config.sessions_dir.glob("*.jsonl")
            if _session_owner_id(p) == user_id
        ]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    def resume_latest(self, user_id: int) -> tuple[bool, str]:
        files = self._sessions_for_user(user_id)
        if not files:
            return False, "No saved sessions for your account."
        warn = self.load_session_file(files[0], user_id)
        msg = f"Resumed {files[0].name} ({len(self.get(user_id).messages)} messages)."
        if warn:
            msg = f"{warn}\n\n{msg}"
        return True, msg

    def resume_named(self, user_id: int, name: str) -> tuple[bool, str]:
        needle = name.lower().strip()
        matches = [
            p
            for p in self.config.sessions_dir.glob("*.jsonl")
            if needle in p.name.lower() and _session_owner_id(p) == user_id
        ]
        if not matches:
            return False, f"No session matching {name!r}."
        path = max(matches, key=lambda p: p.stat().st_mtime)
        warn = self.load_session_file(path, user_id)
        msg = f"Resumed {path.name} ({len(self.get(user_id).messages)} messages)."
        if warn:
            msg = f"{warn}\n\n{msg}"
        return True, msg
