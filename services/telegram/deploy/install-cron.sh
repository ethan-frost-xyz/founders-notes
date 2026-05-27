#!/usr/bin/env bash
# Install nightly sync-and-index crontab on the Mac mini (operator-run).
# Idempotent: replaces an existing founders sync-and-index line if present.
set -euo pipefail

ENV_FILE="${FOUNDERS_TELEGRAM_ENV:-${HOME}/.config/founders-telegram/env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

: "${VAULT_ROOT:?Set VAULT_ROOT in ${ENV_FILE}}"

SYNC_SCRIPT="${VAULT_ROOT}/services/telegram/deploy/sync-and-index.sh"
LOG_DIR="${HOME}/Library/Logs/founders-telegram"
CRON_LINE="0 4 * * * ${SYNC_SCRIPT} >> ${LOG_DIR}/sync.log 2>&1"
MARKER="# founders-telegram-sync-and-index"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--print]

  (default)  Install nightly 4:00 sync-and-index crontab (idempotent).
  --print    Print the cron block without modifying crontab (tests / review).
EOF
}

print_block() {
  echo "${MARKER}"
  echo "${CRON_LINE}"
}

install_cron() {
  mkdir -p "${LOG_DIR}"

  if [[ ! -x "${SYNC_SCRIPT}" ]]; then
    chmod +x "${SYNC_SCRIPT}"
  fi

  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v "${MARKER}" | grep -v "sync-and-index.sh" > "${tmp}" || true
  {
    cat "${tmp}"
    print_block
  } | crontab -
  rm -f "${tmp}"

  echo "Installed crontab entry (4:00 daily):"
  crontab -l | grep -A1 "${MARKER}" || true
  echo "Log: ${LOG_DIR}/sync.log"
}

case "${1:-}" in
  --print)
    print_block
    ;;
  -h|--help)
    usage
    ;;
  "")
    install_cron
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 1
    ;;
esac
