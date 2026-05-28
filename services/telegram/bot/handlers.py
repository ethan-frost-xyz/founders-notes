"""Telegram command and message handlers (thin transport over VaultAgent)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tool_status import tool_status_label
from auth import is_allowed
from config import BotConfig
from sessions import SessionStore
from telegram import Update
from telegram.ext import ContextTypes

from agent import VaultAgent
from messaging import reply_text_chunked


HELP_TEXT = """Founders vault agent

Ask a question in study-notes voice with [ep-NNNN] citations.

Commands:
/start — this help + vault stats
/janitor — daily notes ritual (file → expand → promote)
/librarian — exit Janitor back to Q&A
/cancel — cancel Janitor workflow
/clear — wipe the in-memory thread
/newchat — export thread to catalog/telegram-sessions/ and start fresh
/resume — load the most recent exported session
/resume <name> — load a session by filename fragment
/web <query> — one turn with web search enabled (vault still preferred)

Normal messages use Librarian Q&A. In Janitor mode, messages follow the notes workflow."""


def vault_stats_text(vault_root: Path) -> str:
    catalog_path = vault_root / "catalog" / "episodes.jsonl"
    chunks_path = vault_root / "catalog" / "chunks.jsonl"
    episodes = 0
    if catalog_path.is_file():
        with catalog_path.open(encoding="utf-8") as f:
            episodes = sum(1 for line in f if line.strip())
    indexed = "unknown"
    if chunks_path.is_file():
        mtime = datetime.fromtimestamp(chunks_path.stat().st_mtime, tz=timezone.utc)
        indexed = mtime.strftime("%Y-%m-%d %H:%M UTC")
    return f"Episodes in catalog: {episodes}\nChunks index updated: {indexed}"


def parse_web_query(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.lower().startswith("/web"):
        return None
    rest = stripped[4:].strip()
    return rest if rest else None


async def _reject_unauthorized(update: Update, config: BotConfig) -> bool:
    user = update.effective_user
    if is_allowed(user.id if user else None, config):
        return False
    if update.message:
        await update.message.reply_text("Unauthorized.")
    return True


def _config(context: ContextTypes.DEFAULT_TYPE) -> BotConfig:
    return context.application.bot_data["config"]


def _sessions(context: ContextTypes.DEFAULT_TYPE) -> SessionStore:
    return context.application.bot_data["sessions"]


def _agent(context: ContextTypes.DEFAULT_TYPE) -> VaultAgent:
    return context.application.bot_data["agent"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    stats = vault_stats_text(_config(context).agent.vault_root)
    await reply_text_chunked(update.message, f"{HELP_TEXT}\n\n{stats}")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    _sessions(context).clear(uid)
    await update.message.reply_text("Session cleared.")


async def cmd_newchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    path = _sessions(context).new_chat(uid)
    if path:
        await update.message.reply_text(f"Exported {path.name} and started a new chat.")
    else:
        await update.message.reply_text("No messages to export. Started a fresh chat.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    uid = update.effective_user.id
    args = context.args or []
    if args:
        ok, msg = _sessions(context).resume_named(uid, " ".join(args))
    else:
        ok, msg = _sessions(context).resume_latest(uid)
    await reply_text_chunked(update.message, msg)


async def cmd_web(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /web <query>")
        return
    await _run_agent_turn(update, context, query, allow_web=True)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_unauthorized(update, _config(context)):
        return
    if not update.message or not update.message.text:
        return
    janitor = context.application.bot_data.get("janitor")
    if janitor is not None and janitor.is_active(update.effective_user.id):
        from janitor_handlers import on_janitor_text

        if await on_janitor_text(update, context):
            return
    text = update.message.text.strip()
    web_query = parse_web_query(text)
    if web_query is not None:
        await _run_agent_turn(update, context, web_query, allow_web=True)
        return
    if text.startswith("/"):
        return
    await _run_agent_turn(update, context, text, allow_web=False)


def _is_harness_bot(context: ContextTypes.DEFAULT_TYPE) -> bool:
    bot = context.application.bot
    return getattr(bot, "username", None) == "harness_bot"


async def _run_agent_turn(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    *,
    allow_web: bool,
) -> None:
    uid = update.effective_user.id
    sessions = _sessions(context)
    agent = _agent(context)
    history = sessions.history_for_agent(uid)

    await update.message.reply_chat_action("typing")

    status_msg: Any | None = None
    loop = asyncio.get_running_loop()
    harness = _is_harness_bot(context)

    async def _update_status(label: str) -> None:
        nonlocal status_msg
        if status_msg is None:
            status_msg = await update.message.reply_text(label)
        else:
            try:
                await status_msg.edit_text(label)
            except Exception:
                pass

    def _schedule_status(label: str) -> None:
        asyncio.create_task(_update_status(label))

    def on_tool_start(tool_name: str, _args: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(_schedule_status, tool_status_label(tool_name))

    try:
        result = await asyncio.to_thread(
            agent.run_turn,
            user_text,
            history=history,
            allow_web=allow_web,
            session_id=str(uid),
            on_tool_start=on_tool_start,
        )
    finally:
        if status_msg is not None and not harness:
            try:
                await status_msg.delete()
            except Exception:
                pass

    sessions.append_turn(
        uid,
        user_text=user_text,
        assistant_text=result.content,
        tool_trace=result.tool_trace,
    )
    await reply_text_chunked(update.message, result.content)
