"""Ops runner lock and git pull helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BOT = REPO / "services" / "telegram" / "bot"
import sys

if str(BOT) not in sys.path:
    sys.path.insert(0, str(BOT))

from ops_runner import (  # noqa: E402
    ops_lock_held,
    release_ops_lock,
    run_git_pull,
    try_acquire_ops_lock,
)


def test_ops_lock_single_flight():
    bot_data: dict = {}
    assert try_acquire_ops_lock(bot_data) is True
    assert ops_lock_held(bot_data) is True
    assert try_acquire_ops_lock(bot_data) is False
    release_ops_lock(bot_data)
    assert ops_lock_held(bot_data) is False
    assert try_acquire_ops_lock(bot_data) is True


def test_run_git_pull_not_a_repo(tmp_path: Path):
    code, msg = run_git_pull(tmp_path)
    assert code != 0
    assert msg.strip()
