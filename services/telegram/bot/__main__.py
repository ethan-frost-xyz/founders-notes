"""Run the Founders vault Telegram bot (polling)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# bootstrap lives under bot/; add it before import when run as python -m bot
_BOT_DIR = Path(__file__).resolve().parent
if str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

from bootstrap import setup_telegram_paths

setup_telegram_paths()

from app_factory import build_application  # noqa: E402
from poll_lock import acquire_polling_lock  # noqa: E402

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    acquire_polling_lock()
    app = build_application()
    logger.info("Starting vault bot (polling)")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
