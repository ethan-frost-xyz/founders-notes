#!/usr/bin/env bash
# Refresh vault git checkout and rebuild chunk + embedding indexes.
# Run when the bot is idle (avoid concurrent git pull during agent turns).
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

LOCK_DIR="${VAULT_ROOT}/catalog/.sync-in-progress"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "sync-and-index: skipped (another sync in progress)"
  exit 0
fi
# shellcheck disable=SC2064
trap 'rmdir "${LOCK_DIR}" 2>/dev/null || true' EXIT

echo "sync-and-index: VAULT_ROOT=${VAULT_ROOT}"

# Embed/expand slugs may live only in runtime.json (not env after slim cutover).
eval "$(
  "${PYTHON}" "${VAULT_ROOT}/ingestion/lib/export_runtime_env.py"
)"

cd "${VAULT_ROOT}"
git pull --ff-only

cd "${VAULT_ROOT}/ingestion"
"${PYTHON}" lib/reindex_vault.py

echo "sync-and-index: done"
