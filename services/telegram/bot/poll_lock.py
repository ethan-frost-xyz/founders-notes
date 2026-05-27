"""Ensure only one Telegram polling process runs at a time (prevents 409 Conflict)."""

from __future__ import annotations

import fcntl
import os
import sys
from pathlib import Path


def acquire_polling_lock() -> None:
    lock_dir = Path.home() / "Library" / "Logs" / "founders-telegram"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "bot.poll.lock"
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        print(
            "Another vault bot is already polling Telegram (409 Conflict if both run).\n"
            "Stop the other instance: launchctl bootout gui/$(id -u)/com.founders.telegram.bot\n"
            "or close any terminal running `python -m bot`.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    lock_file.write(f"{os.getpid()}\n")
    lock_file.flush()
    # Hold lock for process lifetime (file stays open until exit).
