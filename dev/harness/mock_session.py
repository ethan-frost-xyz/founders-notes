"""Mock Telegram transport around the real vault bot application."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
TELEGRAM_BOT_DIR = REPO_ROOT / "services" / "telegram" / "bot"
TELEGRAM_TOOLS_DIR = TELEGRAM_BOT_DIR / "tools"
DEFAULT_USER_ID = 999_001
DEFAULT_LOG_DIR = REPO_ROOT / "dev" / "logs"

_PATH_PATCH_KEYS = (
    "ROOT",
    "CATALOG_PATH",
    "CHUNKS_PATH",
    "NOTES_DIR",
    "TRANSCRIPTS_DIR",
    "POSTS_DIR",
)

_update_id = count(1)
_message_id = count(1)


def _ensure_import_paths(vault_root: Path | None = None) -> Path:
    root = vault_root or REPO_ROOT
    os.environ.setdefault("VAULT_ROOT", str(root))
    ingestion = root / "ingestion"
    for entry in (str(ingestion), str(TELEGRAM_BOT_DIR), str(TELEGRAM_TOOLS_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from _bootstrap import resolve_vault_root, setup_ingestion_paths

    resolved = resolve_vault_root(root)
    setup_ingestion_paths(resolved)
    return resolved


@dataclass
class Reply:
    text: str
    parse_mode: str | None = None
    reply_markup: Any = None
    inline_keyboard_buttons: list[str] = field(default_factory=list)


def _buttons_from_markup(reply_markup: Any) -> list[str]:
    if reply_markup is None:
        return []
    inline = getattr(reply_markup, "inline_keyboard", None)
    if not inline:
        return []
    labels: list[str] = []
    for row in inline:
        for btn in row:
            labels.append(getattr(btn, "text", str(btn)))
    return labels


def _reply_from_send_kwargs(kwargs: dict[str, Any]) -> Reply:
    markup = kwargs.get("reply_markup")
    return Reply(
        text=str(kwargs.get("text") or ""),
        parse_mode=kwargs.get("parse_mode"),
        reply_markup=markup,
        inline_keyboard_buttons=_buttons_from_markup(markup),
    )


def _build_agent_config(
    vault_root: Path,
    *,
    llm_mode: Literal["live", "echo"],
) -> Any:
    from config import AgentConfig

    if llm_mode == "live":
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        model = os.environ.get("TELEGRAM_CHAT_MODEL", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for live LLM mode")
        if not model:
            raise ValueError("TELEGRAM_CHAT_MODEL is required for live LLM mode")
    else:
        api_key = "harness-echo-key"
        model = "harness/echo"

    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"

    return AgentConfig(
        api_key=api_key,
        model=model,
        vault_root=vault_root,
        openrouter_base_url=base_url.rstrip("/"),
    )


def _build_bot_config(
    agent_cfg: Any,
    *,
    user_id: int,
    sessions_dir: Path,
) -> Any:
    from config import BotConfig

    janitor_clean = os.environ.get("JANITOR_CLEAN_MODEL", "").strip() or None
    if agent_cfg.model == "harness/echo":
        janitor_clean = janitor_clean or "harness/echo"
    elif not janitor_clean:
        janitor_clean = os.environ.get("TELEGRAM_CHAT_MODEL", "").strip() or None
    return BotConfig(
        agent=agent_cfg,
        telegram_token="0:fake",
        allowed_user_ids=frozenset({user_id}),
        sessions_dir=sessions_dir,
        janitor_clean_model=janitor_clean,
    )


def _install_echo_llm() -> list[Any]:
    """Patch OpenRouter clients for Librarian + Janitor clean + expand subprocess."""

    def _echo_completion(**kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = str(msg.get("content") or "")
                break
        content = f"[harness echo] {user_text[:400]}"
        if kwargs.get("stream"):
            delta = SimpleNamespace(content=content, tool_calls=None)

            def _gen():
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return _gen()
        assistant = SimpleNamespace(content=content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=assistant)])

    class _EchoCompletions:
        def create(self, **kwargs: Any) -> Any:
            return _echo_completion(**kwargs)

    class _EchoChat:
        completions = _EchoCompletions()

    class _EchoOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        @property
        def chat(self) -> _EchoChat:
            return _EchoChat()

    def _echo_call_openrouter(**kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            content="## Raw datapoints\n\n- wealth is assets (2:00)\n- happiness is a skill (8:00)\n"
        )

    def _stub_run_expand(vault_root: Path, episode_id: str, *, force: bool) -> tuple[int, str]:
        from catalog import load_catalog, resolve_catalog_row as _resolve
        import paths as vault_paths

        row = _resolve(load_catalog(), episode_id)
        ep_id = row["id"]
        slug = row["slug"]
        num = row.get("episode_number")
        draft = vault_paths.expanded_draft_file_path(ep_id, slug, num)
        draft.parent.mkdir(parents=True, exist_ok=True)
        if not draft.is_file() or force:
            draft.write_text(
                f"---\nepisode_id: {ep_id}\nsource: harness_stub\n---\n\n"
                "## Expanded datapoints\n\n"
                "### — Harness stub datapoint\n\n"
                "Quote: Stub quote for harness testing.\n\n"
                "Key takeaway: Stub takeaway.\n",
                encoding="utf-8",
            )
        return 0, "stub expand ok"

    def _stub_run_reindex(vault_root: Path) -> tuple[int, str]:
        _ = vault_root
        return 0, "stub reindex ok"

    patches = [
        patch("openai.OpenAI", _EchoOpenAI),
        patch("openrouter_client.call_openrouter", _echo_call_openrouter),
        patch("janitor_workflow.run_expand", _stub_run_expand),
        patch("janitor_handlers.run_expand", _stub_run_expand),
        patch("janitor_workflow.run_reindex", _stub_run_reindex),
        patch("janitor_handlers.run_reindex", _stub_run_reindex),
    ]
    for p in patches:
        p.start()
    return patches


async def _register_bot_commands(application: Any) -> None:
    from telegram import BotCommand

    await application.bot.set_my_commands(
        [
            BotCommand("start", "Help and vault stats"),
            BotCommand("janitor", "Notes ritual: file → expand → promote"),
            BotCommand("librarian", "← Back from Janitor to Q&A"),
            BotCommand("cancel", "Cancel Janitor workflow"),
            BotCommand("clear", "Clear in-memory chat thread"),
            BotCommand("newchat", "Export session and reset"),
            BotCommand("resume", "Resume exported session"),
        ]
    )


def _build_application(bot_cfg: Any, agent: Any, sessions: Any, janitor: Any) -> Any:
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

    from handlers import (
        cmd_clear,
        cmd_newchat,
        cmd_resume,
        cmd_start,
        on_text,
    )
    from janitor_handlers import (
        cmd_cancel,
        cmd_janitor,
        cmd_librarian,
        on_janitor_callback,
    )

    app = (
        Application.builder()
        .token(bot_cfg.telegram_token)
        .post_init(_register_bot_commands)
        .build()
    )
    app.bot_data["config"] = bot_cfg
    app.bot_data["agent"] = agent
    app.bot_data["sessions"] = sessions
    app.bot_data["janitor"] = janitor

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("janitor", cmd_janitor))
    app.add_handler(CommandHandler("librarian", cmd_librarian))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("newchat", cmd_newchat))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CallbackQueryHandler(on_janitor_callback, pattern=r"^janitor:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return app


class MockBotSession:
    """Drive the real Telegram bot handlers with a mocked Bot API transport."""

    def __init__(
        self,
        *,
        vault_root: Path | None = None,
        user_id: int = DEFAULT_USER_ID,
        log_dir: Path | None = None,
        llm_mode: Literal["live", "echo"] = "live",
        janitor_sandbox: Any | None = None,
    ) -> None:
        self.user_id = user_id
        self.llm_mode = llm_mode
        self.log_dir = (log_dir or DEFAULT_LOG_DIR).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / "sessions").mkdir(parents=True, exist_ok=True)

        effective_vault = vault_root or REPO_ROOT
        if janitor_sandbox is not None:
            effective_vault = janitor_sandbox.vault_root
        self.vault_root = _ensure_import_paths(effective_vault)
        self.janitor_sandbox = janitor_sandbox

        self.replies: list[Reply] = []
        self.tool_traces: list[dict[str, Any]] = []
        self._echo_patches: list[Any] = []
        self._paths_patch: Any | None = None
        self._app: Any = None
        self._chat: Any = None
        self._user: Any = None
        self._last_bot_message: Any = None

    def _capture_reply(self, kwargs: dict[str, Any]) -> Reply:
        reply = _reply_from_send_kwargs(kwargs)
        self.replies.append(reply)
        return reply

    def _wire_mock_bot(self, app: Any) -> None:
        session = self

        class _HarnessMockBot:
            username = "harness_bot"
            id = 1

            async def initialize(self) -> None:
                return None

            async def shutdown(self) -> None:
                return None

            async def get_me(self) -> Any:
                return SimpleNamespace(
                    id=self.id,
                    is_bot=True,
                    username=self.username,
                    first_name="Harness",
                )

            async def send_message(self, *args: Any, **kwargs: Any) -> Any:
                return await session._fake_send_message(*args, **kwargs)

            async def send_chat_action(self, *args: Any, **kwargs: Any) -> bool:
                return True

            async def edit_message_text(self, *args: Any, **kwargs: Any) -> Any:
                return await session._fake_edit_message(*args, **kwargs)

            async def answer_callback_query(self, *args: Any, **kwargs: Any) -> bool:
                return True

        mock_bot = _HarnessMockBot()
        app.bot = mock_bot
        if getattr(app, "updater", None) is not None:
            app.updater.bot = mock_bot

    async def _fake_send_message(self, *args: Any, **kwargs: Any) -> Any:
        from telegram import Message

        captured = self._capture_reply(kwargs)
        self._last_bot_message = Message(
            message_id=next(_message_id),
            date=datetime.now(timezone.utc),
            chat=self._chat,
            text=captured.text,
        )
        self._last_bot_message.set_bot(self._app.bot)
        return self._last_bot_message

    async def _fake_edit_message(self, *args: Any, **kwargs: Any) -> Any:
        from telegram import Message

        captured = self._capture_reply(kwargs)
        self._last_bot_message = Message(
            message_id=next(_message_id),
            date=datetime.now(timezone.utc),
            chat=self._chat,
            text=captured.text,
        )
        self._last_bot_message.set_bot(self._app.bot)
        return self._last_bot_message

    def _wrap_agent(self, agent: Any) -> Any:
        original = agent.run_turn
        traces = self.tool_traces

        def run_turn(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            if result.tool_trace:
                traces.extend(result.tool_trace)
            return result

        agent.run_turn = run_turn  # type: ignore[method-assign]
        return agent

    def _apply_paths_patch(self) -> None:
        if self.janitor_sandbox is None:
            return
        import paths as vault_paths

        saved = {k: getattr(vault_paths, k) for k in _PATH_PATCH_KEYS}
        root = self.janitor_sandbox.vault_root
        vault_paths.ROOT = root
        vault_paths.CATALOG_PATH = root / "catalog" / "episodes.jsonl"
        vault_paths.CHUNKS_PATH = root / "catalog" / "chunks.jsonl"
        vault_paths.NOTES_DIR = root / "content" / "notes"
        vault_paths.TRANSCRIPTS_DIR = root / "content" / "transcripts"
        vault_paths.POSTS_DIR = root / "content" / "posts"
        self._paths_patch = (vault_paths, saved)

    def _restore_paths_patch(self) -> None:
        if not self._paths_patch:
            return
        vault_paths, saved = self._paths_patch
        for key, value in saved.items():
            setattr(vault_paths, key, value)
        self._paths_patch = None

    async def start(self) -> None:
        from agent import VaultAgent
        from janitor_store import JanitorStore
        from sessions import SessionStore
        from telegram import Chat, User

        if self.llm_mode == "echo":
            self._echo_patches = _install_echo_llm()

        self._apply_paths_patch()

        agent_cfg = _build_agent_config(self.vault_root, llm_mode=self.llm_mode)
        bot_cfg = _build_bot_config(
            agent_cfg,
            user_id=self.user_id,
            sessions_dir=self.log_dir / "sessions",
        )
        agent = VaultAgent(agent_cfg)
        self._wrap_agent(agent)
        sessions = SessionStore(bot_cfg)
        janitor = JanitorStore()

        self._app = _build_application(bot_cfg, agent, sessions, janitor)
        self._wire_mock_bot(self._app)
        await self._app.initialize()

        self._user = User(id=self.user_id, first_name="Harness", is_bot=False)
        self._chat = Chat(id=self.user_id, type=Chat.PRIVATE)

    async def shutdown(self) -> None:
        if self._app is not None:
            await self._app.shutdown()
            self._app = None
        for p in self._echo_patches:
            p.stop()
        self._echo_patches = []
        self._restore_paths_patch()

    async def __aenter__(self) -> MockBotSession:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.shutdown()

    def _make_message_update(self, text: str) -> Any:
        from telegram import Message, MessageEntity, Update

        entities = None
        if text.startswith("/"):
            command = text.split()[0]
            entities = [
                MessageEntity(
                    type=MessageEntity.BOT_COMMAND,
                    offset=0,
                    length=len(command),
                )
            ]
        msg = Message(
            message_id=next(_message_id),
            date=datetime.now(timezone.utc),
            chat=self._chat,
            from_user=self._user,
            text=text,
            entities=entities,
        )
        msg.set_bot(self._app.bot)
        return Update(update_id=next(_update_id), message=msg)

    def _make_callback_update(self, callback_data: str) -> Any:
        from telegram import CallbackQuery, Message, Update

        if self._last_bot_message is not None and isinstance(self._last_bot_message, Message):
            message = self._last_bot_message
        else:
            message = Message(
                message_id=next(_message_id),
                date=datetime.now(timezone.utc),
                chat=self._chat,
                text="(harness preview)",
            )
            message.set_bot(self._app.bot)
        query = CallbackQuery(
            id=str(next(_update_id)),
            from_user=self._user,
            chat_instance=str(self.user_id),
            data=callback_data,
            message=message,
        )
        query.set_bot(self._app.bot)
        return Update(update_id=next(_update_id), callback_query=query)

    async def send(self, text: str) -> list[Reply]:
        if self._app is None:
            raise RuntimeError("Session not started; use async with MockBotSession()")
        self.replies.clear()
        await self._app.process_update(self._make_message_update(text))
        return list(self.replies)

    async def tap_button(self, callback_data: str) -> list[Reply]:
        if self._app is None:
            raise RuntimeError("Session not started; use async with MockBotSession()")
        self.replies.clear()
        await self._app.process_update(self._make_callback_update(callback_data))
        return list(self.replies)

    async def reset(self) -> None:
        if self._app is None:
            return
        self.replies.clear()
        self.tool_traces.clear()
        self._app.bot_data["sessions"].clear(self.user_id)
        self._app.bot_data["janitor"].reset(self.user_id)

    def janitor_phase(self) -> str | None:
        if self._app is None:
            return None
        session = self._app.bot_data["janitor"].get(self.user_id)
        return session.phase.value

    def update_vault_root(self, vault_root: Path) -> None:
        """Rebuild bot_data config when Janitor sandbox vault changes mid-session."""
        if self._app is None:
            return
        from config import AgentConfig, BotConfig

        old_cfg = self._app.bot_data["config"]
        agent_cfg = AgentConfig(
            api_key=old_cfg.agent.api_key,
            model=old_cfg.agent.model,
            vault_root=vault_root,
            max_tool_result_chars=old_cfg.agent.max_tool_result_chars,
            openrouter_base_url=old_cfg.agent.openrouter_base_url,
            default_search_k=old_cfg.agent.default_search_k,
        )
        bot_cfg = BotConfig(
            agent=agent_cfg,
            telegram_token=old_cfg.telegram_token,
            allowed_user_ids=old_cfg.allowed_user_ids,
            sessions_dir=old_cfg.sessions_dir,
            janitor_clean_model=old_cfg.janitor_clean_model,
        )
        self._app.bot_data["config"] = bot_cfg
        from agent import VaultAgent

        agent = VaultAgent(agent_cfg)
        self._wrap_agent(agent)
        self._app.bot_data["agent"] = agent
        self.vault_root = vault_root


@asynccontextmanager
async def mock_session(
    **kwargs: Any,
) -> AsyncIterator[MockBotSession]:
    session = MockBotSession(**kwargs)
    async with session:
        yield session
