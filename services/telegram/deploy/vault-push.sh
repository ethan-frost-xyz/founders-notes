#!/usr/bin/env bash
# Commit and push whitelisted vault changes from the Mac mini (pull-first, no force).
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

LOCK_DIR="${VAULT_ROOT}/catalog/.vault-push-in-progress"
COMMIT_MSG="vault: push from Mac mini"
EPISODE_ID=""
DRY_RUN=0
SKIP_VERIFY=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Pull --ff-only, optionally run verify.py, stage whitelisted paths, commit, push.

Options:
  -m MESSAGE       Commit message (default: vault: push from Mac mini)
  --episode ID     Janitor scope: stage only content/notes/{folder}/ for ep-NNNN
  --dry-run        Print actions without commit/push
  --skip-verify    Skip pipeline/verify.py
  -h, --help       Show this help

Exit codes: 0 ok or nothing to commit; 1 pull/push/verify failure; 2 lock held
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m)
      COMMIT_MSG="${2:?-m requires a message}"
      shift 2
      ;;
    --episode)
      EPISODE_ID="${2:?--episode requires ep-NNNN}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-verify)
      SKIP_VERIFY=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "vault-push: skipped (another vault-push in progress)"
  exit 2
fi
# shellcheck disable=SC2064
trap 'rmdir "${LOCK_DIR}" 2>/dev/null || true' EXIT

echo "vault-push: VAULT_ROOT=${VAULT_ROOT}"

cd "${VAULT_ROOT}"

if [[ "${DRY_RUN}" -eq 0 ]]; then
  git pull --ff-only
else
  echo "vault-push: [dry-run] would run: git pull --ff-only"
fi

NOTES_DIR=""
if [[ -n "${EPISODE_ID}" ]]; then
  NOTES_DIR="$(
    EPISODE_ID="${EPISODE_ID}" VAULT_ROOT="${VAULT_ROOT}" "${PYTHON}" <<'PY'
import os
import sys
from pathlib import Path

vault_root = Path(os.environ["VAULT_ROOT"])
ep = os.environ["EPISODE_ID"]
sys.path.insert(0, str(vault_root / "ingestion"))
from _bootstrap import setup_ingestion_paths

setup_ingestion_paths(vault_root)
from catalog import load_catalog, resolve_catalog_row
import paths as vault_paths

row = resolve_catalog_row(load_catalog(), ep)
folder = vault_paths.folder_name(row["id"], row["slug"], row.get("episode_number"))
print(vault_root / "content" / "notes" / folder)
PY
  )" || {
    echo "vault-push: failed to resolve episode ${EPISODE_ID}" >&2
    exit 1
  }
fi

RUN_VERIFY=0
if [[ "${SKIP_VERIFY}" -eq 0 && -z "${EPISODE_ID}" ]]; then
  RUN_VERIFY=1
fi

if [[ "${RUN_VERIFY}" -eq 1 ]]; then
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    (cd "${VAULT_ROOT}/ingestion" && "${PYTHON}" pipeline/verify.py)
  else
    echo "vault-push: [dry-run] would run: pipeline/verify.py"
  fi
fi

stage_paths() {
  if [[ -n "${EPISODE_ID}" ]]; then
    if [[ ! -d "${NOTES_DIR}" ]]; then
      echo "vault-push: episode notes dir missing: ${NOTES_DIR}" >&2
      return 1
    fi
    git add "${NOTES_DIR}/"
    echo "vault-push: staged ${NOTES_DIR}/"
    return 0
  fi

  git add content/notes/

  local pattern path
  shopt -s nullglob
  for pattern in \
    dev/logs/runs/*-report.json \
    dev/logs/runs/*-report.md \
    dev/logs/runs/*-librarian-live-suite-summary.json \
    dev/logs/runs/*-librarian-live-suite-rerun-summary.json; do
    for path in ${pattern}; do
      git add "${path}"
      echo "vault-push: staged ${path}"
    done
  done
  shopt -u nullglob

  if [[ "${RUN_VERIFY}" -eq 1 && -f catalog/gaps.md ]]; then
    git add catalog/gaps.md
    echo "vault-push: staged catalog/gaps.md"
  fi
}

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "vault-push: [dry-run] would stage whitelisted paths"
  if [[ -n "${EPISODE_ID}" ]]; then
    echo "vault-push: [dry-run] episode scope: ${NOTES_DIR}/"
  fi
  git status --short -- content/notes/ dev/logs/runs/ catalog/gaps.md 2>/dev/null || true
  echo "vault-push: [dry-run] would commit: ${COMMIT_MSG}"
  echo "vault-push: [dry-run] would run: git push"
  exit 0
fi

stage_paths

if git diff --cached --quiet; then
  echo "vault-push: no whitelisted changes to commit"
  exit 0
fi

git commit -m "${COMMIT_MSG}"
git push
echo "vault-push: committed and pushed"
