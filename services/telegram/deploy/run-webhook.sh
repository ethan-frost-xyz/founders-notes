#!/usr/bin/env bash
# Start the GitHub webhook listener (used by launchd). Sources founders-telegram env.
set -euo pipefail

ENV_FILE="${FOUNDERS_TELEGRAM_ENV:-${HOME}/.config/founders-telegram/env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

: "${VAULT_ROOT:?Set VAULT_ROOT in ${ENV_FILE}}"
: "${GITHUB_WEBHOOK_SECRET:?Set GITHUB_WEBHOOK_SECRET in ${ENV_FILE}}"

PYTHON="${VAULT_ROOT}/ingestion/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

exec "${PYTHON}" "${VAULT_ROOT}/services/telegram/deploy/github_webhook_server.py"
