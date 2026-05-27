#!/usr/bin/env bash
# Single-instance bot restart for Mac mini (launchd).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"${SCRIPT_DIR}/stop-bot.sh"
PLIST="${HOME}/Library/LaunchAgents/com.founders.telegram.bot.plist"
LABEL="gui/$(id -u)/com.founders.telegram.bot"

if [[ -f "${PLIST}" ]]; then
  launchctl bootstrap "${LABEL%/*}" "${PLIST}" 2>/dev/null || true
  launchctl enable "${LABEL}" 2>/dev/null || true
  launchctl kickstart -k "${LABEL}"
  echo "launchd bot restarted."
else
  echo "No ${PLIST} — run SP4 install or start manually via run-bot.sh" >&2
  exit 1
fi
