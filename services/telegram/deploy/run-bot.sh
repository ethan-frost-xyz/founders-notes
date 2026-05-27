#!/usr/bin/env bash
# Start the vault Telegram bot (used by launchd). Sources ~/.config/founders-telegram/env.
set -euo pipefail

ENV_FILE="${FOUNDERS_TELEGRAM_ENV:-${HOME}/.config/founders-telegram/env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

: "${VAULT_ROOT:?Set VAULT_ROOT in ${ENV_FILE}}"

PYTHON="${VAULT_ROOT}/ingestion/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

cd "${VAULT_ROOT}/services/telegram"
exec "${PYTHON}" -m bot
