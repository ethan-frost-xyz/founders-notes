"""Telegram message size helpers (Bot API text limit)."""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from telegram.constants import ParseMode

# https://core.telegram.org/bots/api#sendmessage
TELEGRAM_MESSAGE_LIMIT = 4096

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")


def markdown_to_telegram_html(text: str) -> str:
    """Convert a small markdown subset to Telegram HTML (escape-safe)."""
    placeholders: list[str] = []

    def stash(html_fragment: str) -> str:
        key = f"\x00TG{len(placeholders)}\x00"
        placeholders.append(html_fragment)
        return key

    def bold_sub(match: re.Match[str]) -> str:
        return stash(f"<b>{html.escape(match.group(1))}</b>")

    def code_sub(match: re.Match[str]) -> str:
        return stash(f"<code>{html.escape(match.group(1))}</code>")

    converted = _BOLD_RE.sub(bold_sub, text)
    converted = _CODE_RE.sub(code_sub, converted)
    converted = html.escape(converted)
    for idx, fragment in enumerate(placeholders):
        converted = converted.replace(f"\x00TG{idx}\x00", fragment)
    return converted


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
        await message.reply_text(
            markdown_to_telegram_html(part),
            parse_mode=ParseMode.HTML,
        )
