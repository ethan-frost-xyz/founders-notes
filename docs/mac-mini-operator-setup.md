# Mac mini operator setup

Step-by-step checklist after merging **laptop remote hardening** (SP5 webhook + sync-script runtime env). Run on the **Mac mini** unless noted.

**Prerequisites:** `founders-notes` clone, `ingestion/.venv`, `~/.config/founders-telegram/env` with secrets, bot already working via launchd.

## Quick reference (this machine)

Repo on disk:

```text
/Users/ethanfrost/projects/my-github-projects/founders-podcast-brain/founders-notes
```

`VAULT_ROOT` in `~/.config/founders-telegram/env` should match that path. Deploy scripts read it after:

```bash
set -a && source ~/.config/founders-telegram/env && set +a
```

Then `$VAULT_ROOT/...` is just shorthand for the repo root — not a separate “vault” install.

---

## Part A — Runtime cutover (if not done after PR #12)

Do this before relying on cron/webhook for embeddings.

### A1. Pull latest `main`

```bash
cd "$VAULT_ROOT"   # e.g. ~/founders-notes
git fetch origin
git checkout main
git pull --ff-only origin main
```

Confirm the log mentions runtime-config / laptop-remote-hardening merge.

### A2. Restart the Telegram bot

```bash
"$VAULT_ROOT/services/telegram/deploy/restart-bot.sh"
# or:
launchctl kickstart -k "gui/$(id -u)/com.founders.telegram.bot"
```

Check logs if it does not come back:

```bash
tail -30 ~/Library/Logs/founders-telegram/bot.stderr.log
```

### A3. Verify `/settings` on Telegram

On your phone (allowlisted account), send **`/settings`**.

You should see model lines with source **`runtime.json`** (not only `env …`). Example:

```text
embed_model: qwen/... (runtime.json)
librarian_model: ... (runtime.json)
```

If models still show only `env TELEGRAM_CHAT_MODEL`, send one `/setmodel` or restart again after confirming `~/.config/founders-telegram/runtime.json` exists.

### A4. Slim `~/.config/founders-telegram/env`

Edit env so it keeps **secrets and paths only**:

| Keep | Remove (after runtime.json has values) |
|------|----------------------------------------|
| `VAULT_ROOT` | `TELEGRAM_CHAT_MODEL` |
| `TELEGRAM_BOT_TOKEN` | `JANITOR_CLEAN_MODEL` |
| `TELEGRAM_ALLOWED_USER_IDS` | `OPENROUTER_MODEL` |
| `OPENROUTER_API_KEY` | `OPENROUTER_EMBED_MODEL` |
| | `TELEGRAM_MAX_STEPS` |

Template: [`services/telegram/deploy/env.example`](../services/telegram/deploy/env.example).

Restart bot after editing env.

### A5. Smoke `/sync`

When the bot is **idle** (no Janitor draft, no active Librarian turn):

1. Send **`/sync`** on Telegram.
2. Wait for success (pull + reindex).
3. Send **`/sync`** again immediately — second message should say another op is already running **or** complete quickly if the first finished.

### A6. Confirm nightly cron (optional)

```bash
"$VAULT_ROOT/services/telegram/deploy/install-cron.sh" --print
crontab -l | grep founders-telegram
```

You should see `0 4 * * *` and `sync-and-index.sh`.

### A7. Smoke `sync-and-index.sh` with slim env

With model slugs **removed** from env (only in `runtime.json`):

```bash
set -a && source ~/.config/founders-telegram/env && set +a
"$VAULT_ROOT/services/telegram/deploy/sync-and-index.sh"
```

Must complete without `OPENROUTER_EMBED_MODEL` missing errors.

**Part A done when:** `/settings` shows runtime sources; manual script and `/sync` both finish reindex.

---

## Part B — GitHub webhook (SP5)

GitHub cannot reach a private Tailscale IP. Use **Tailscale Funnel** → localhost webhook listener.

### B1. Generate webhook secret

On the Mac mini:

```bash
openssl rand -hex 32
```

Add to `~/.config/founders-telegram/env`:

```bash
GITHUB_WEBHOOK_SECRET=<paste-hex-here>
# optional (defaults shown):
# GITHUB_WEBHOOK_PORT=9876
# GITHUB_WEBHOOK_HOST=127.0.0.1
```

```bash
chmod 600 ~/.config/founders-telegram/env
```

### B2. Enable Tailscale Funnel

```bash
# Default listener port must match GITHUB_WEBHOOK_PORT (9876)
tailscale funnel --bg http://127.0.0.1:9876
tailscale funnel status
```

Note the **HTTPS URL** (e.g. `https://something.ts.net`). Webhook path is **`/github`** → full URL:

```text
https://<your-funnel-host>/github
```

To disable later: `tailscale funnel off`.

### B3. Install webhook launchd job

```bash
set -a && source ~/.config/founders-telegram/env && set +a
chmod +x "$VAULT_ROOT/services/telegram/deploy/install-webhook.sh"
"$VAULT_ROOT/services/telegram/deploy/install-webhook.sh"
```

Verify:

```bash
launchctl print "gui/$(id -u)/com.founders.telegram.webhook" | head -20
tail -5 ~/Library/Logs/founders-telegram/webhook.log
```

### B4. Configure GitHub repository webhook

In GitHub: **Repository → Settings → Webhooks → Add webhook**

| Field | Value |
|-------|--------|
| Payload URL | `https://<funnel-host>/github` |
| Content type | `application/json` |
| Secret | Same as `GITHUB_WEBHOOK_SECRET` |
| SSL verification | Enable |
| Events | **Just the push event** |

Save. GitHub sends a **ping** — check `webhook.log` for activity.

### B5. End-to-end smoke test

1. On laptop: merge a trivial change to **`main`** (or empty commit on `main`).
2. On Mac mini within ~10 minutes:

```bash
tail -30 ~/Library/Logs/founders-telegram/webhook.log
tail -30 ~/Library/Logs/founders-telegram/sync.log
cd "$VAULT_ROOT" && git log -1 --oneline
```

3. `HEAD` on mini should match GitHub `main`.

### B6. Concurrency check (optional)

While `sync-and-index.sh` is running (watch `sync.log`), push again or run script manually — second run should log **skipped (another sync in progress)** and exit 0.

**Part B done when:** push to `main` updates Mac mini without SSH or `/sync`.

---

## Fallback

Until Part B works: after every merge to `main`, send Telegram **`/sync`** when the bot is idle.

---

## Laptop side (reference)

No Mac mini steps. See [laptop-development.md](laptop-development.md): branch → `pytest tests -q` → PR → merge.

---

## Related

- [services/telegram/README.md](../services/telegram/README.md) — deploy reference
- [manual-operations.md](manual-operations.md) — when to refresh index
- [`.cursor/plans/laptop_remote_hardening.plan.md`](../.cursor/plans/laptop_remote_hardening.plan.md) — architecture
