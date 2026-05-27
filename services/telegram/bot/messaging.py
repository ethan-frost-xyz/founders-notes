"""Telegram message size helpers (Bot API text limit)."""

from __future__ import annotations

from typing import TYPE_CHECKING

# https://core.telegram.org/bots/api#sendmessage
TELEGRAM_MESSAGE_LIMIT = 4096


def split_telegram_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split text into parts each <= limit, preferring paragraph and line breaks."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    rest = text
    min_break = max(limit // 4, 1)

    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break

        window = rest[:limit]
        split_at = window.rfind("\n\n")
        if split_at < min_break:
            split_at = window.rfind("\n")
        if split_at < min_break:
            split_at = window.rfind(" ")
        if split_at <= 0:
            split_at = limit

        chunk = rest[:split_at]
        if not chunk:
            split_at = limit
            chunk = rest[:split_at]

        chunks.append(chunk)
        rest = rest[split_at:]
        if rest.startswith(" "):
            rest = rest[1:]

    return chunks


if TYPE_CHECKING:
    from telegram import Message


async def reply_text_chunked(message: Message, text: str) -> None:
    for part in split_telegram_text(text):
        await message.reply_text(part)
