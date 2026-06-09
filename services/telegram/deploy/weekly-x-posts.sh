#!/usr/bin/env bash
# Weekly X post sync + attribute + optional git commit (Mac mini).
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

LOCK_DIR="${VAULT_ROOT}/catalog/.x-posts-sync-in-progress"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "weekly-x-posts: skipped (another X sync in progress)"
  exit 0
fi
# shellcheck disable=SC2064
trap 'rmdir "${LOCK_DIR}" 2>/dev/null || true' EXIT

echo "weekly-x-posts: VAULT_ROOT=${VAULT_ROOT}"

cd "${VAULT_ROOT}"
git pull --ff-only

cd "${VAULT_ROOT}/ingestion"
"${PYTHON}" x/x_posts_sync.py --initial-window 10
"${PYTHON}" x/x_posts_attribute.py --llm-review
"${PYTHON}" pipeline/verify.py

cd "${VAULT_ROOT}"
if ! git diff --quiet -- content/posts/ catalog/gaps.md catalog/post-mapping-review.jsonl catalog/x-posts-pending.jsonl; then
  git add content/posts/ catalog/gaps.md catalog/post-mapping-review.jsonl catalog/x-posts-pending.jsonl
  git commit -m "vault: sync X posts (weekly cron)"
  git push
  echo "weekly-x-posts: committed and pushed"
else
  echo "weekly-x-posts: no content changes to commit"
fi

echo "weekly-x-posts: done"
