#!/usr/bin/env bash
# Stop all vault Telegram bot pollers (launchd + stray terminals). Safe to run before local dev.
set -euo pipefail

LABEL="gui/$(id -u)/com.founders.telegram.bot"
launchctl bootout "${LABEL}" 2>/dev/null || true
pkill -f "Python -m bot" 2>/dev/null || true
sleep 1
pkill -9 -f "Python -m bot" 2>/dev/null || true
rm -f "${HOME}/Library/Logs/founders-telegram/bot.poll.lock"
echo "Stopped launchd bot (if loaded) and terminal pollers."
