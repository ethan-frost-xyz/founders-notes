"""Run the Founders vault Telegram bot (polling)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure bot/ and tools/ importable when run as python -m bot
_BOT_DIR = Path(__file__).resolve().parent
_TOOLS_DIR = _BOT_DIR / "tools"
for entry in (str(_BOT_DIR), str(_TOOLS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

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
from sessions import SessionStore  # noqa: E402

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application():
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    bot_config = load_bot_config()
    agent = VaultAgent(bot_config.agent)
    sessions = SessionStore(bot_config)

    app = (
        Application.builder()
        .token(bot_config.telegram_token)
        .build()
    )
    app.bot_data["config"] = bot_config
    app.bot_data["agent"] = agent
    app.bot_data["sessions"] = sessions

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("newchat", cmd_newchat))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("web", cmd_web))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return app


def main() -> None:
    app = build_application()
    logger.info("Starting vault bot (polling)")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
