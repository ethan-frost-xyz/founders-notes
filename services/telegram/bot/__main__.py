"""Run the Founders vault Telegram bot (polling)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure bot/ and tools/ importable when run as python -m bot
_BOT_DIR = Path(__file__).resolve().parent
_TOOLS_DIR = _BOT_DIR / "tools"
for entry in (str(_BOT_DIR), str(_TOOLS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)


def _bootstrap_vault_paths() -> None:
    """Janitor and vault tools import ingestion/lib (episode_ids, catalog, …)."""
    env = os.environ.get("VAULT_ROOT", "").strip()
    vault = Path(env).resolve() if env else _BOT_DIR.resolve().parents[2]
    ingestion = vault / "ingestion"
    if str(ingestion) not in sys.path:
        sys.path.insert(0, str(ingestion))
    from _bootstrap import resolve_vault_root, setup_ingestion_paths

    setup_ingestion_paths(resolve_vault_root())


_bootstrap_vault_paths()

from agent import VaultAgent  # noqa: E402
from config import load_bot_config  # noqa: E402
from handlers import (  # noqa: E402
    cmd_clear,
    cmd_newchat,
    cmd_resume,
    cmd_start,
    cmd_web,
    on_text,
)
from janitor_handlers import (  # noqa: E402
    cmd_cancel,
    cmd_janitor,
    cmd_librarian,
    on_janitor_callback,
)
from janitor_store import JanitorStore  # noqa: E402
from poll_lock import acquire_polling_lock  # noqa: E402
from sessions import SessionStore  # noqa: E402

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _register_bot_commands(application) -> None:
    from telegram import BotCommand

    await application.bot.set_my_commands(
        [
            BotCommand("start", "Help and vault stats"),
            BotCommand("janitor", "Notes ritual: file → expand → promote"),
            BotCommand("librarian", "Exit Janitor to Q&A"),
            BotCommand("cancel", "Cancel Janitor workflow"),
            BotCommand("clear", "Clear in-memory chat thread"),
            BotCommand("newchat", "Export session and reset"),
            BotCommand("resume", "Resume exported session"),
            BotCommand("web", "One turn with web search enabled"),
        ]
    )


def build_application():
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

    bot_config = load_bot_config()
    agent = VaultAgent(bot_config.agent)
    sessions = SessionStore(bot_config)
    janitor = JanitorStore()

    app = (
        Application.builder()
        .token(bot_config.telegram_token)
        .post_init(_register_bot_commands)
        .build()
    )
    app.bot_data["config"] = bot_config
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
    app.add_handler(CommandHandler("web", cmd_web))
    app.add_handler(CallbackQueryHandler(on_janitor_callback, pattern=r"^janitor:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return app


def main() -> None:
    acquire_polling_lock()
    app = build_application()
    logger.info("Starting vault bot (polling)")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
