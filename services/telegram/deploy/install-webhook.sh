#!/usr/bin/env bash
# Install launchd job for GitHub push webhook (operator-run on Mac mini).
set -euo pipefail

ENV_FILE="${FOUNDERS_TELEGRAM_ENV:-${HOME}/.config/founders-telegram/env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

: "${VAULT_ROOT:?Set VAULT_ROOT in ${ENV_FILE}}"

PLIST_SRC="${VAULT_ROOT}/services/telegram/deploy/com.founders.telegram.webhook.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/com.founders.telegram.webhook.plist"
RUN_WEBHOOK="${VAULT_ROOT}/services/telegram/deploy/run-webhook.sh"
LOG_DIR="${HOME}/Library/Logs/founders-telegram"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--print]

  (default)  Install com.founders.telegram.webhook launchd job (idempotent).
  --print    Print plist label and paths without modifying launchd (tests / review).
EOF
}

print_info() {
  echo "Label: com.founders.telegram.webhook"
  echo "Plist: ${PLIST_DST}"
  echo "Runner: ${RUN_WEBHOOK}"
  echo "Logs: ${LOG_DIR}/webhook.log"
  echo "Listener: http://127.0.0.1:\${GITHUB_WEBHOOK_PORT:-9876}/github"
}

install_webhook() {
  mkdir -p "${LOG_DIR}"
  chmod +x "${RUN_WEBHOOK}" "${VAULT_ROOT}/services/telegram/deploy/github_webhook_server.py"

  sed \
    -e "s|REPLACE_WITH_VAULT_ROOT|${VAULT_ROOT}|g" \
    -e "s|REPLACE_WITH_HOME|${HOME}|g" \
    "${PLIST_SRC}" > "${PLIST_DST}"

  launchctl bootout "gui/$(id -u)" "${PLIST_DST}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${PLIST_DST}"
  launchctl enable "gui/$(id -u)/com.founders.telegram.webhook"

  echo "Installed webhook launchd job:"
  print_info
}

case "${1:-}" in
  --print)
    print_info
    ;;
  -h|--help)
    usage
    ;;
  "")
    install_webhook
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 1
    ;;
esac
