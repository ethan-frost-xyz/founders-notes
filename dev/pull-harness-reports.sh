#!/usr/bin/env bash
# Pull harness reports (dev/logs/runs/*) from the Mac mini over Tailscale SSH.
# On the mini you can instead Telegram /push or vault-push.sh; laptop uses this to sync before commit.
#
# Run from the laptop repo root after a remote librarian live suite:
#   ./dev/pull-harness-reports.sh
#   ./dev/pull-harness-reports.sh --list
#   ./dev/pull-harness-reports.sh --latest-json | jq '.scenarios[] | {name, passed}'
#
# Override host or mini repo path:
#   FOUNDERS_MINI_HOST=my-mini FOUNDERS_MINI_REPO=/path/to/repo ./dev/pull-harness-reports.sh
set -euo pipefail

MINI_HOST="${FOUNDERS_MINI_HOST:-ethans-mac-mini}"
MINI_REPO="${FOUNDERS_MINI_REPO:-/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
REMOTE_RUNS="${MINI_REPO}/dev/logs/runs"
LOCAL_RUNS="${LOCAL_REPO}/dev/logs/runs"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Pull librarian harness reports from the Mac mini (Tailscale SSH).

Options:
  --list          List newest report files on the mini (no download)
  --latest-json   Print the newest *-report.json from the mini to stdout
  --latest-md     Print the newest *-report.md from the mini to stdout
  -h, --help      Show this help

Environment:
  FOUNDERS_MINI_HOST   SSH host (default: ethans-mac-mini)
  FOUNDERS_MINI_REPO   Repo path on the mini (default: mini production path)

Default (no flags): rsync dev/logs/runs/ from mini → local dev/logs/runs/
EOF
}

remote_ls() {
  ssh "${MINI_HOST}" "test -d '${REMOTE_RUNS}'" || {
    echo "No reports directory on ${MINI_HOST}:${REMOTE_RUNS}" >&2
    exit 1
  }
  ssh "${MINI_HOST}" "ls -lt '${REMOTE_RUNS}' | head -25"
}

remote_latest() {
  local pattern="$1"
  ssh "${MINI_HOST}" "ls -t '${REMOTE_RUNS}'/${pattern} 2>/dev/null | head -1"
}

pull_reports() {
  mkdir -p "${LOCAL_RUNS}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -avz "${MINI_HOST}:${REMOTE_RUNS}/" "${LOCAL_RUNS}/"
  else
    scp -r "${MINI_HOST}:${REMOTE_RUNS}/." "${LOCAL_RUNS}/"
  fi
  echo "Synced → ${LOCAL_RUNS}"
}

case "${1:-}" in
  --list)
    remote_ls
    ;;
  --latest-json)
    path="$(remote_latest '*-report.json')"
    if [[ -z "${path}" ]]; then
      echo "No *-report.json on ${MINI_HOST}" >&2
      exit 1
    fi
    ssh "${MINI_HOST}" "cat '${path}'"
    ;;
  --latest-md)
    path="$(remote_latest '*-report.md')"
    if [[ -z "${path}" ]]; then
      echo "No *-report.md on ${MINI_HOST}" >&2
      exit 1
    fi
    ssh "${MINI_HOST}" "cat '${path}'"
    ;;
  -h | --help)
    usage
    ;;
  "")
    pull_reports
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 1
    ;;
esac
