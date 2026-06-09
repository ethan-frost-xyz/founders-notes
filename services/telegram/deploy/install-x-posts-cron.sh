#!/usr/bin/env bash
# Install weekly X posts crontab on the Mac mini (operator-run).
# Idempotent: replaces an existing founders weekly-x-posts line if present.
set -euo pipefail

ENV_FILE="${FOUNDERS_TELEGRAM_ENV:-${HOME}/.config/founders-telegram/env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

: "${VAULT_ROOT:?Set VAULT_ROOT in ${ENV_FILE}}"

WEEKLY_SCRIPT="${VAULT_ROOT}/services/telegram/deploy/weekly-x-posts.sh"
LOG_DIR="${HOME}/Library/Logs/founders-telegram"
CRON_LINE="0 5 * * 0 ${WEEKLY_SCRIPT} >> ${LOG_DIR}/x-posts.log 2>&1"
MARKER="# founders-telegram-weekly-x-posts"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--print]

  (default)  Install weekly Sunday 5:00 X posts sync crontab (idempotent).
  --print    Print the cron block without modifying crontab (tests / review).
EOF
}

print_block() {
  echo "${MARKER}"
  echo "${CRON_LINE}"
}

install_cron() {
  mkdir -p "${LOG_DIR}"

  if [[ ! -x "${WEEKLY_SCRIPT}" ]]; then
    chmod +x "${WEEKLY_SCRIPT}"
  fi

  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v "${MARKER}" | grep -v "weekly-x-posts.sh" > "${tmp}" || true
  {
    cat "${tmp}"
    print_block
  } | crontab -
  rm -f "${tmp}"

  echo "Installed crontab entry (Sunday 5:00):"
  crontab -l | grep -A1 "${MARKER}" || true
  echo "Log: ${LOG_DIR}/x-posts.log"
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
