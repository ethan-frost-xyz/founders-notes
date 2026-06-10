"""Librarian free-text turn: streaming, status labels, session persistence."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from agent import VaultAgent
from context import agent as get_agent, sessions as get_sessions
from messaging import TELEGRAM_MESSAGE_LIMIT, reply_text_chunked
from runtime_settings import effective_stream_replies
from telegram import Update
from telegram.ext import ContextTypes
from tool_status import tool_status_label
from turn_timing import TurnTimer, append_timing_jsonl, is_timing_enabled


def _is_harness_bot(context: ContextTypes.DEFAULT_TYPE) -> bool:
    bot = context.application.bot
    return getattr(bot, "username", None) == "harness_bot"


async def run_librarian_turn(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
) -> None:
    uid = update.effective_user.id
    sessions = get_sessions(context)
    agent: VaultAgent = get_agent(context)
    history = sessions.history_for_agent(uid)

    t_handler = perf_counter()
    harness = _is_harness_bot(context)
    timer: TurnTimer | None = None
    if is_timing_enabled(harness=harness):
        timer = TurnTimer()
        if not harness and update.message and update.message.date:
            pickup_ms = max(
                0,
                int((t_handler - update.message.date.timestamp()) * 1000),
            )
            timer.set_telegram_pickup_ms(pickup_ms)

    await update.message.reply_chat_action("typing")

    status_msg: Any | None = None
    stream_msg: Any | None = None
    accumulated_text = ""
    last_stream_edit_at = 0.0
    loop = asyncio.get_running_loop()
    stream_enabled, _ = effective_stream_replies()
    stream_lock = asyncio.Lock()

    async def _flush_stream(text: str) -> None:
        nonlocal stream_msg, last_stream_edit_at
        async with stream_lock:
            now = loop.time()
            if stream_msg is None:
                stream_msg = await update.message.reply_text(text or "…")
                last_stream_edit_at = now
            elif now - last_stream_edit_at >= 0.5:
                try:
                    await stream_msg.edit_text(text or "…")
                except Exception:
                    pass
                last_stream_edit_at = now

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

    def _schedule_stream_flush(t: str) -> None:
        asyncio.create_task(_flush_stream(t))

    def on_tool_start(tool_name: str, _args: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(_schedule_status, tool_status_label(tool_name))

    def on_chunk(delta: str) -> None:
        nonlocal accumulated_text
        accumulated_text += delta
        text = accumulated_text
        loop.call_soon_threadsafe(_schedule_stream_flush, text)

    try:
        result = await asyncio.to_thread(
            agent.run_turn,
            user_text,
            history=history,
            session_id=str(uid),
            on_tool_start=on_tool_start,
            on_chunk=on_chunk if stream_enabled else None,
            timing=timer,
        )
    finally:
        if status_msg is not None and not harness:
            try:
                await status_msg.delete()
            except Exception:
                pass

    if timer is not None and not harness and is_timing_enabled(harness=False):
        append_timing_jsonl(timer.to_dict(), session_id=str(uid))

    if stream_msg is not None and not harness:
        preview = result.content or "…"
        if len(preview) > TELEGRAM_MESSAGE_LIMIT:
            preview = preview[:TELEGRAM_MESSAGE_LIMIT]
        async with stream_lock:
            try:
                await stream_msg.edit_text(preview)
            except Exception:
                pass
        try:
            await stream_msg.delete()
        except Exception:
            pass

    sessions.append_turn(
        uid,
        user_text=user_text,
        assistant_text=result.content,
        tool_trace=result.tool_trace,
    )
    await reply_text_chunked(update.message, result.content)
