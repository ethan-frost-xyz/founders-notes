"""Build python-telegram-bot Application for production and harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from agent import VaultAgent
from config import BotConfig, load_bot_config
from handlers import (
    cmd_clear,
    cmd_newchat,
    cmd_pull,
    cmd_reindex,
    cmd_resetcleantemp,
    cmd_resetmodel,
    cmd_restart,
    cmd_resume,
    cmd_setcleantemp,
    cmd_setmodel,
    cmd_settings,
    cmd_start,
    cmd_sync,
    on_text,
)
from janitor_handlers import (
    cmd_cancel,
    cmd_janitor,
    cmd_librarian,
    on_janitor_callback,
)
from janitor_store import JanitorStore
from sessions import SessionStore
from settings_handlers import on_settings_callback


CommandSet = Literal["production", "harness"]


@dataclass
class AppOptions:
    include_settings: bool = True
    include_ops: bool = True
    command_set: CommandSet = "production"


def _production_commands() -> list[Any]:
    from telegram import BotCommand

    return [
        BotCommand("start", "Vault stats"),
        BotCommand("janitor", "Notes ritual"),
        BotCommand("settings", "Models, temp, stream, ops"),
        BotCommand("sync", "Pull + reindex"),
        BotCommand("newchat", "Export session, reset"),
        BotCommand("restart", "Restart bot"),
    ]


def _harness_commands() -> list[Any]:
    from telegram import BotCommand

    return [
        BotCommand("start", "Help and vault stats"),
        BotCommand("janitor", "Notes ritual: file → expand → promote"),
        BotCommand("librarian", "← Back from Janitor to Q&A"),
        BotCommand("cancel", "Cancel Janitor workflow"),
        BotCommand("clear", "Clear in-memory chat thread"),
        BotCommand("newchat", "Export session and reset"),
        BotCommand("resume", "Resume exported session"),
    ]


async def _register_bot_commands(application: Any, commands: list[Any]) -> None:
    await application.bot.set_my_commands(commands)


def build_application(
    options: AppOptions | None = None,
    *,
    bot_config: BotConfig | None = None,
    agent: VaultAgent | None = None,
    sessions: SessionStore | None = None,
    janitor: JanitorStore | None = None,
) -> Any:
    """Wire handlers. Pass pre-built services for harness injection."""
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

    opts = options or AppOptions()
    bot_cfg = bot_config or load_bot_config()
    vault_agent = agent or VaultAgent(bot_cfg.agent)
    session_store = sessions or SessionStore(bot_cfg)
    janitor_store = janitor or JanitorStore()

    commands = (
        _harness_commands() if opts.command_set == "harness" else _production_commands()
    )

    async def post_init(application: Any) -> None:
        await _register_bot_commands(application, commands)

    app = (
        Application.builder()
        .token(bot_cfg.telegram_token)
        .post_init(post_init)
        .build()
    )
    app.bot_data["config"] = bot_cfg
    app.bot_data["agent"] = vault_agent
    app.bot_data["sessions"] = session_store
    app.bot_data["janitor"] = janitor_store

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("janitor", cmd_janitor))
    app.add_handler(CommandHandler("librarian", cmd_librarian))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("newchat", cmd_newchat))
    app.add_handler(CommandHandler("resume", cmd_resume))

    if opts.include_settings:
        app.add_handler(CommandHandler("settings", cmd_settings))
        app.add_handler(CommandHandler("setmodel", cmd_setmodel))
        app.add_handler(CommandHandler("resetmodel", cmd_resetmodel))
        app.add_handler(CommandHandler("setcleantemp", cmd_setcleantemp))
        app.add_handler(CommandHandler("resetcleantemp", cmd_resetcleantemp))
        app.add_handler(CallbackQueryHandler(on_settings_callback, pattern=r"^set:"))

    if opts.include_ops:
        app.add_handler(CommandHandler("pull", cmd_pull))
        app.add_handler(CommandHandler("reindex", cmd_reindex))
        app.add_handler(CommandHandler("sync", cmd_sync))
        app.add_handler(CommandHandler("restart", cmd_restart))

    app.add_handler(CallbackQueryHandler(on_janitor_callback, pattern=r"^janitor:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return app


HARNESS_APP_OPTIONS = AppOptions(
    include_settings=False,
    include_ops=False,
    command_set="harness",
)
