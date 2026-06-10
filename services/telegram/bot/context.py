"""Shared Telegram handler context: auth, config reload, typed bot_data access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auth import is_allowed
from config import BotConfig, load_bot_config
from janitor_store import JanitorStore
from sessions import SessionStore
from telegram import Update
from telegram.ext import ContextTypes

from agent import VaultAgent


@dataclass
class BotContext:
    """Typed view over ``application.bot_data``."""

    config: BotConfig
    agent: VaultAgent
    sessions: SessionStore
    janitor: JanitorStore
    raw: dict[str, Any]

    @classmethod
    def from_application(cls, application: Any) -> BotContext:
        data = application.bot_data
        return cls(
            config=data["config"],
            agent=data["agent"],
            sessions=data["sessions"],
            janitor=data["janitor"],
            raw=data,
        )


def bot_context(context: ContextTypes.DEFAULT_TYPE) -> BotContext:
    return BotContext.from_application(context.application)


def config(context: ContextTypes.DEFAULT_TYPE) -> BotConfig:
    return bot_context(context).config


def sessions(context: ContextTypes.DEFAULT_TYPE) -> SessionStore:
    return bot_context(context).sessions


def agent(context: ContextTypes.DEFAULT_TYPE) -> VaultAgent:
    return bot_context(context).agent


def janitor_store(context: ContextTypes.DEFAULT_TYPE) -> JanitorStore:
    return bot_context(context).janitor


def reload_bot_config(context: ContextTypes.DEFAULT_TYPE) -> tuple[BotConfig, VaultAgent]:
    bot_config = load_bot_config()
    new_agent = VaultAgent(bot_config.agent)
    data = context.application.bot_data
    data["config"] = bot_config
    data["agent"] = new_agent
    return bot_config, new_agent


async def reject_unauthorized(update: Update, bot_cfg: BotConfig) -> bool:
    """Return True when the user must be rejected (unauthorized)."""
    user = update.effective_user
    if is_allowed(user.id if user else None, bot_cfg):
        return False
    if update.callback_query:
        await update.callback_query.answer("Unauthorized.", show_alert=True)
    elif update.message:
        await update.message.reply_text("Unauthorized.")
    return True
