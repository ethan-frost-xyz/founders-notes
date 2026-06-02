---
name: Telegram ops sync (SP5)
overview: GitHub push webhook on Mac mini → background sync-and-index.sh via Tailscale Funnel. Shipped with laptop-remote-hardening.
todos:
  - id: sync-script-runtime-env
    content: export_runtime_env.py + sync-and-index.sh lock + runtime exports
    status: completed
  - id: webhook-server
    content: github_webhook_server.py, run-webhook.sh, launchd plist, install-webhook.sh
    status: completed
  - id: webhook-tests
    content: test_github_webhook.py + deploy smoke tests
    status: completed
  - id: docs
    content: laptop-development.md, manual-ops, telegram README, vault-agent, potential-ideas
    status: completed
  - id: mac-mini-install
    content: "Operator: Funnel URL, GITHUB_WEBHOOK_SECRET, install-webhook.sh, smoke push to main"
    status: completed
isProject: false
---

# SP5 — GitHub webhook → vault sync

**Status:** Shipped on `main` (May 2026). Operator guide: [`docs/mac-mini-operator-setup.md`](../../../docs/mac-mini-operator-setup.md). Do not implement from this archive unless restoring history.

**Parent:** [laptop_remote_hardening.plan.md](laptop_remote_hardening.plan.md)

## Contracts

| Item | Value |
|------|--------|
| Events | `push` only; `ping` → 200 during setup |
| Branch | `refs/heads/main` only |
| Response | 202 + background `sync-and-index.sh` (GitHub ~10s timeout) |
| Auth | `X-Hub-Signature-256` HMAC with `GITHUB_WEBHOOK_SECRET` |
| Listen | `127.0.0.1:${GITHUB_WEBHOOK_PORT:-9876}/github` |
| Exposure | Tailscale Funnel → public HTTPS → localhost listener |
| Concurrency | `catalog/.sync-in-progress` mkdir lock in `sync-and-index.sh` |
| Process | `com.founders.telegram.webhook` launchd (not polling bot) |
| Logs | `~/Library/Logs/founders-telegram/webhook.log`, `sync.log` |

## Operator install

1. `GITHUB_WEBHOOK_SECRET` in `~/.config/founders-telegram/env`
2. `tailscale funnel --bg http://127.0.0.1:9876` (or chosen port/path)
3. GitHub → Settings → Webhooks → `https://<funnel-host>/github`, secret, push events only
4. `services/telegram/deploy/install-webhook.sh`
5. Merge to `main` → verify `webhook.log`, `sync.log`, `git log -1`

**Fallback:** Telegram `/sync` when webhook or Funnel is down. Production install completed May 2026 — see [`docs/mac-mini-operator-setup.md`](../../../docs/mac-mini-operator-setup.md).

## Out of scope (v1)

- Path-filtered reindex
- `/resume` auto-sync
- Replacing nightly cron
- Handler integration tests for `/sync`
