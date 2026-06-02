# Mac mini operator guide

**Status (May 2026):** Production stack is live on **Ethans-Mac-mini** — launchd bot + webhook, Tailscale Funnel, GitHub push → `sync-and-index.sh`, `runtime.json` models, git over **SSH**.

This doc is the **day-to-day and recovery** guide. First-time install steps are in [Initial setup (reference)](#initial-setup-reference) below.

---

## Where each thing happens

| Task | Where |
|------|--------|
| Edit code / notes, PR, merge to `main` | **Laptop** (Cursor) |
| Auto `git pull` + reindex after merge | **Mac mini** (webhook) — wait ~2–5 min |
| Janitor, Librarian, `/sync`, `/settings` | **Phone** (Telegram) |
| Webhook URL, secret, delivery status | **GitHub** → repo → Settings → Webhooks |
| Bot + webhook processes, Funnel, logs | **Mac mini** (Terminal) |
| Model slugs (primary) | **Mac mini** file `~/.config/founders-telegram/runtime.json` (or `/setmodel` on phone) |
| Secrets (token, API key, repo path) | **Mac mini** file `~/.config/founders-telegram/env` — **not in git** |

**Do not** run `python -m bot` on the **laptop** with the production token while the Mac mini bot is running (Telegram **409 Conflict**).

---

## Paths on this Mac mini

| What | Path |
|------|------|
| Repo (git checkout) | `/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes` |
| Telegram secrets env | `~/.config/founders-telegram/env` |
| Models + tuning (`max_steps`, `stream_replies`, Janitor temp) | `~/.config/founders-telegram/runtime.json` |
| Bot logs | `~/Library/Logs/founders-telegram/bot.stdout.log`, `bot.stderr.log` |
| Webhook + sync logs | `~/Library/Logs/founders-telegram/webhook.log`, `sync.log` |
| Git remote | `git@github.com:ethan-frost-xyz/founders-notes.git` (SSH) |

`VAULT_ROOT` in env is set to the repo path above. Deploy scripts use it after `source ~/.config/founders-telegram/env`.

---

## Normal workflow (nothing to “start” daily)

1. **Laptop:** branch → `pytest tests -q` → PR → merge **`main`**.
2. **Mac mini:** webhook pulls and reindexes automatically.
3. **Phone:** `/janitor` for daily notes; Librarian when you want Q&A.

**Fallback** if webhook fails: Telegram **`/sync`** when the bot is idle.

Laptop dev details: [laptop-development.md](laptop-development.md).

**Bot/code changes after a merge:** webhook updates files only — you must **`/restart`** (or the restart block below) before testing new Python. Full loop: [remote-product-workflow.md](remote-product-workflow.md).

---

## Mac mini — status & restart (paste in Terminal)

Use on **Ethans-Mac-mini** only. Restarts bot + webhook; does not start a second terminal poller.

```bash
REPO="/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes"
ENV="$HOME/.config/founders-telegram/env"
GUI="gui/$(id -u)"

set -a && source "$ENV" && set +a

echo "=== launchd ==="
launchctl print "$GUI/com.founders.telegram.bot" 2>/dev/null | grep "state =" || echo "BOT: not loaded"
launchctl print "$GUI/com.founders.telegram.webhook" 2>/dev/null | grep "state =" || echo "WEBHOOK: not loaded"
tailscale funnel status 2>/dev/null | head -6 || echo "(install tailscale CLI if missing)"

echo "=== restart ==="
"$REPO/services/telegram/deploy/restart-bot.sh"
launchctl kickstart -k "$GUI/com.founders.telegram.webhook"

sleep 2
echo "=== logs ==="
tail -8 "$HOME/Library/Logs/founders-telegram/bot.stderr.log" 2>/dev/null
tail -5 "$HOME/Library/Logs/founders-telegram/webhook.log" 2>/dev/null
```

Expect both jobs `state = running`. `launchctl kickstart` prints nothing on success.

---

## Verify GitHub webhook (browser)

1. https://github.com/ethan-frost-xyz/founders-notes/settings/hooks  
2. Open the webhook (`…ts.net/github`).  
3. **Recent Deliveries** → latest **ping** should be **200**; **push** to `main` should be **202**.

Ping **401** → secret in GitHub does not match `GITHUB_WEBHOOK_SECRET` in `~/.config/founders-telegram/env`; fix, then `launchctl kickstart -k gui/$(id -u)/com.founders.telegram.webhook`.

---

## Bad merge on `main`

Restart alone does **not** fix broken code on disk.

1. **Laptop:** revert PR or merge a fix to `main` on GitHub.  
2. **Mac mini:** webhook pulls the fix (or send **`/sync`** on Telegram).  
3. **Mac mini:** run the [restart block](#mac-mini--status--restart-paste-in-terminal) if the bot still crashes.

You do **not** need a second bot on the laptop to recover.

---

## Troubleshooting

| Symptom | Where | Fix |
|---------|--------|-----|
| Merge didn’t update mini | GitHub → Webhooks deliveries | Ping must be 200; push 202; then check `sync.log` on mini |
| `could not read Username` in `sync.log` | Mac mini | `git remote` must be SSH; `ssh -T git@github.com` → `Hi ethan-frost-xyz!` |
| `409 Conflict` in Telegram | Mac mini | Only one poller: `stop-bot.sh` before any terminal `python -m bot` |
| Bot down after reboot | Mac mini | Run restart block above; launchd usually auto-starts at login |
| Funnel / webhook dead | Mac mini | `tailscale funnel --bg http://127.0.0.1:9876` |
| Wrong models | Phone | `/settings`; `/setmodel`; or edit `runtime.json` + restart bot |
| Stale Librarian answers | Phone | `/sync` when idle after content merge |
| Reindex failed: `same shape` / `np.stack` | Mac mini `sync.log` | Usually **embed model changed** with a stale index. Merge current `main` (self-heal in `build_embeddings.py`), then webhook or Telegram **`/sync`** when idle — no manual `rm` needed. SSH fallback: delete `catalog/embeddings.npy`, `embeddings-manifest.jsonl`, `embeddings-meta.json`, then `python lib/reindex_vault.py` from `ingestion/` |

Deploy reference: [services/telegram/README.md](../services/telegram/README.md).

---

## Initial setup (reference)

Use when rebuilding a new Mac mini or after a clean OS install.

### A — Runtime + git (Mac mini)

1. Clone repo; `python3 -m venv ingestion/.venv`; install requirements (see [telegram README](../services/telegram/README.md)).  
2. Copy `services/telegram/deploy/env.example` → `~/.config/founders-telegram/env`; set `VAULT_ROOT`, token, allowlist, API key.  
3. `git remote set-url origin git@github.com:ethan-frost-xyz/founders-notes.git`; add SSH key to GitHub; `git pull --ff-only`.  
4. Install bot launchd (SP4); set models via `/setmodel` or `runtime.json`; **remove model lines from env**.  
5. `install-cron.sh` (optional nightly 4:00).  
6. Smoke: `sync-and-index.sh` and Telegram `/sync`.

### B — Webhook (Mac mini + GitHub)

1. `GITHUB_WEBHOOK_SECRET` in env (`openssl rand -hex 32`).  
2. `tailscale funnel --bg http://127.0.0.1:9876` → note HTTPS host.  
3. `install-webhook.sh`.  
4. GitHub webhook: `https://<funnel-host>/github`, same secret, push events only.  
5. Redeliver ping → 200; merge to `main` → check `sync.log`.

Plans: [telegram_ops_sync.plan.md](../.cursor/plans/archive/telegram_ops_sync.plan.md), [laptop_remote_hardening.plan.md](../.cursor/plans/archive/laptop_remote_hardening.plan.md).

---

## Related

- [remote-product-workflow.md](remote-product-workflow.md) — remote product work end-to-end  
- [laptop-development.md](laptop-development.md) — laptop-only dev loop  
- [manual-operations.md](manual-operations.md) — index refresh matrix  
- [janitor.md](janitor.md) — daily notes on Telegram  
- [telegram-vault-agent.md](telegram-vault-agent.md) — architecture overview  
