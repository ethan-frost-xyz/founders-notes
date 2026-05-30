---
name: Telegram Vault SP4 — Mac mini ops
overview: "launchd, sync-and-index.sh, env template, ops README. Depends on SP3 bot runnable."
todos:
  - id: sync-script
    content: services/telegram/deploy/sync-and-index.sh — git pull + build_chunks + build_embeddings
    status: completed
  - id: launchd
    content: services/telegram/deploy/com.founders.telegram.bot.plist + load instructions
    status: completed
  - id: env-template
    content: services/telegram/deploy/env.example → template for ~/.config/founders-telegram/env
    status: completed
  - id: ops-readme
    content: services/telegram/README.md — install, cron, manual sync, troubleshooting
    status: completed
isProject: false
---

# SP4 — Mac mini ops

**Contracts (live docs):** [docs/telegram-vault-agent.md](../../../docs/telegram-vault-agent.md)  
**Requires:** [telegram_vault_sp3_telegram.plan.md](telegram_vault_sp3_telegram.plan.md)  
**Deferred (shipped):** [telegram_ops_sync.plan.md](telegram_ops_sync.plan.md) — SP5 webhook  
**Branch:** `feature/telegram-vault-bot` · **Commit:** SP4 only · then **PR → `main`**

## Agent handoff

Ops and deploy artifacts only. Do **not** change agent logic or tool contracts unless fixing a deploy blocker.

## Goal

Always-on Mac mini: bot via `launchd`, index refresh via manual/cron script (no GitHub webhook in v0).

## Deliverables

| Path | Purpose |
|------|---------|
| [`services/telegram/deploy/sync-and-index.sh`](../../services/telegram/deploy/sync-and-index.sh) | `cd $VAULT_ROOT && git pull && cd ingestion && python search/build_chunks.py && python search/build_embeddings.py` |
| [`services/telegram/deploy/com.founders.telegram.bot.plist`](../../services/telegram/deploy/com.founders.telegram.bot.plist) | `launchd` — `VAULT_ROOT`, env file, working directory |
| [`services/telegram/deploy/env.example`](../../services/telegram/deploy/env.example) | Template → copy to `~/.config/founders-telegram/env` on Mac mini |
| [`services/telegram/README.md`](../../services/telegram/README.md) | Install, `launchctl load`, cron example, sync cadence |

## `sync-and-index.sh`

- Non-interactive; exit non-zero on failure.
- Assumes `VAULT_ROOT` and Python venv or system `python3` on PATH (document which).
- **v0.1 note:** avoid concurrent `git pull` during an active agent turn — document “run sync when idle”; file lock deferred.

## `launchd`

- Label: `com.founders.telegram.bot` (or repo-agreed name).
- `KeepAlive` / `RunAtLoad` as appropriate for polling bot.
- `StandardOutPath` / `StandardErrorPath` under `~/Library/Logs/founders-telegram/` (document paths).

## Cron (optional, documented)

Example: daily `sync-and-index.sh` at 04:00 local — user enables manually.

## Post-SP4 PR checklist

- [ ] SP1–SP4 commits on `feature/telegram-vault-bot` (one commit per SP)
- [ ] Each SP commit includes its own sub-plan `.plan.md` (SP1 with SP1 commit, etc.); this SP4 commit includes `telegram_vault_sp4_ops.plan.md`
- [ ] `pytest` + `verify.py` green
- [ ] PR description links [vault-agent-v0-checklist.md](../../../docs/vault-agent-v0-checklist.md) + verify-this table

## Commit message

`feat(telegram): SP4 Mac mini launchd and sync-and-index ops`
