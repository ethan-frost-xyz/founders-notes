"""Shared async vault ops (pull / reindex / sync) for Telegram commands and settings panel."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardMarkup, Message
from ui_keyboards import back_to_settings_markup

_MAX_RESULT_CHARS = 3500


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_RESULT_CHARS:
        return text
    return text[: _MAX_RESULT_CHARS - 20] + "\n… (truncated)"


def _lock_busy_reply() -> str:
    return "Another op is already running. Try again later."


async def _acquire_lock(bot_data: dict[str, Any]) -> bool:
    from ops_runner import ops_lock_held, try_acquire_ops_lock

    if ops_lock_held(bot_data):
        return False
    return try_acquire_ops_lock(bot_data)


def _release_lock(bot_data: dict[str, Any]) -> None:
    from ops_runner import release_ops_lock

    release_ops_lock(bot_data)


async def run_ops_job(
    message: Message,
    bot_data: dict[str, Any],
    vault_root: Path,
    *,
    label: str,
    fn: Callable[[Path], tuple[int, str]],
    started: str | None = None,
) -> None:
    """Run an op from a command handler (reply-based status)."""
    if not await _acquire_lock(bot_data):
        await message.reply_text(_lock_busy_reply())
        return
    start_line = started or f"{label} started."
    await message.reply_text(start_line)
    try:
        code, msg = await asyncio.to_thread(fn, vault_root)
    finally:
        _release_lock(bot_data)
    prefix = "Done" if code == 0 else f"Failed (exit {code})"
    from messaging import reply_text_chunked

    await reply_text_chunked(message, f"{prefix}: {label}\n{_truncate(msg)}")


async def run_ops_job_edit(
    message: Message,
    bot_data: dict[str, Any],
    vault_root: Path,
    *,
    label: str,
    fn: Callable[[Path], tuple[int, str]],
    running_text: str,
    back_markup=None,
) -> None:
    """Run an op from settings inline panel (edit same message for status)."""
    if not await _acquire_lock(bot_data):
        await message.edit_text(_lock_busy_reply(), reply_markup=back_to_settings_markup())
        return
    await message.edit_text(running_text)
    try:
        code, msg = await asyncio.to_thread(fn, vault_root)
    finally:
        _release_lock(bot_data)
    prefix = "Done" if code == 0 else f"Failed (exit {code})"
    body = f"{prefix}: {label}\n\n{_truncate(msg)}"
    markup = back_markup if back_markup is not None else back_to_settings_markup()
    await message.edit_text(body, reply_markup=markup)


async def run_ops_restart(message: Message) -> None:
    """Restart bot process; cannot edit message after exit."""
    import os

    await message.edit_text("Restarting…")

    def _exit_process() -> None:
        os._exit(0)

    asyncio.get_running_loop().call_later(2.0, _exit_process)
