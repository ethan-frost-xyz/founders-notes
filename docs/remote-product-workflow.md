# Remote product work (laptop → Mac mini → Telegram)

Use this when you change **product code** — bot handlers, ingestion scripts the bot calls, prompts in repo, deploy scripts, tests — and you want to try it on the **real** Telegram bot on the Mac mini while editing on your **laptop**.

This guide is **not** about daily notes, posts, or transcript content. Content updates do not need a bot restart.

---

## The one rule

After new **code** is on the Mac mini disk, the bot must **exit and start again** before you are testing that build.

| Action | Gets new files on disk? | Loads new Python in the bot? |
|--------|-------------------------|----------------------------|
| Merge to `main` + GitHub webhook | Yes (~2–5 min) | **No** |
| Telegram `/sync` or `/pull` | Yes (when idle) | **No** |
| Telegram `/restart` (or Settings → Restart) | No | **Yes** |
| Mac mini `deploy/restart-bot.sh` | No | **Yes** |

Webhook and `/sync` only run `git pull` + reindex. They never restart the bot process.

---

## Where work happens

| Place | Role |
|-------|------|
| **Laptop** | Edit, `pytest`, PR, merge to `main` |
| **GitHub** | Source of truth; webhook notifies mini on push to `main` |
| **Mac mini** | Git checkout, launchd bot, webhook listener, indexes |
| **Phone (Telegram)** | Test Librarian/Janitor; `/sync`, `/restart` when allowed |

Only **one** process may poll Telegram with the production token (usually launchd on the mini). Do not run `python -m bot` on the laptop with that token while the mini bot is up — you get **409 Conflict**.

---

## Happy path (every product change)

### Phase A — Laptop (before production)

1. **Branch** off `main`: `git checkout -b feature/...`
2. **Edit** code under `services/telegram/`, `ingestion/`, `dev/`, etc.
3. **Test locally** (no Telegram, no production token):
   ```bash
   pytest tests -q
   # If you touched Telegram handlers:
   python dev/mock_telegram_cli.py --stub-llm --run-scenarios
   ```
4. **Open PR** → review → **merge to `main`** on GitHub.

You are not done. The mini is still running the old bot until Phase C.

### Phase B — Mac mini gets the files (automatic or manual)

**Default:** GitHub webhook runs `sync-and-index.sh` on the mini (~2–5 minutes after merge).

**Confirm pull happened** (pick one):

- **GitHub:** [Webhooks](https://github.com/ethan-frost-xyz/founders-notes/settings/hooks) → your hook → **Recent Deliveries** → latest push to `main` → **202**.
- **Mac mini** (SSH or local Terminal): `tail -20 ~/Library/Logs/founders-telegram/sync.log` — should show a recent successful run.
- **Telegram** (if webhook is slow or failed): wait until bot is **idle** (no Janitor in progress), send **`/sync`**. Reply should end with success; that run includes `git pull`.

**Optional:** If you only changed bot code and not vault content, reindex from `/sync` is harmless but not required for testing handler changes.

### Phase C — Restart the bot (required for code)

From Telegram (allowlisted account only):

1. Make sure you are **not** mid-Janitor (finish or `/cancel`).
2. Send **`/restart`** (or `/settings` → Ops → **Restart**).
3. Wait **5–30 seconds** (bot is briefly offline).
4. Send **`/start`** — you should get help + vault stats again.

You are now running Python imported from the checkout **after** the last pull.

### Phase D — Smoke test on Telegram

Minimal checks after a bot change:

| Check | What it proves |
|-------|----------------|
| `/start` | Process up, catalog readable |
| One Librarian question | Handler + search path |
| `/settings` | Ops panel, `runtime.json` path |
| If you changed Janitor | `/janitor` → `/cancel` (don’t need to finish a full episode) |

Deeper checks: [vault-agent-v0-checklist.md](vault-agent-v0-checklist.md). Local depth before merge: [telegram-mock-harness.md](telegram-mock-harness.md).

---

## Checklist card (print in your head)

```
[ ] Merged to main on GitHub
[ ] Mini has new commit (webhook 202 or /sync OK)
[ ] /restart
[ ] /start works
[ ] Feature you changed behaves differently than before
```

Skip the restart line only if you did **not** change anything under `services/telegram/` or other code the running bot imports.

---

## Changes that need extra steps

| Change | After pull | After restart |
|--------|------------|---------------|
| Python bot handlers only | — | Test in Telegram |
| New pip dependency on mini | SSH: `ingestion/.venv/bin/pip install -r ingestion/requirements.txt` | `/restart` |
| `runtime.json` model slugs | — | `/setmodel` hot-reloads some roles; restart if unsure |
| Embed model slug | `/reindex` or `/sync` when idle | — |
| Secrets in `~/.config/founders-telegram/env` | Edit on **mini** | `/restart` or `restart-bot.sh` |
| Broken code on `main` | Fix on laptop → merge fix | `/sync` then `/restart` |

---

## Hiccups (what to do)

### 1. “I merged but behavior didn’t change”

Most common: **forgot `/restart`**, or pull never ran.

1. Confirm mini has the commit: SSH `cd $VAULT_ROOT && git log -1 --oneline` and match GitHub `main`.
2. If old commit: fix webhook (below) or Telegram **`/sync`** when idle.
3. Send **`/restart`**, then **`/start`**, test again.

### 2. Webhook didn’t fire or pull failed

**Symptoms:** GitHub delivery not **202**; `sync.log` shows errors; `/sync` says failed.

| Cause | Fix |
|-------|-----|
| Delivery **401** | `GITHUB_WEBHOOK_SECRET` on mini must match GitHub webhook secret; `launchctl kickstart -k gui/$(id -u)/com.founders.telegram.webhook` |
| Funnel down | On mini: `tailscale funnel --bg http://127.0.0.1:9876` |
| `could not read Username` in `sync.log` | Mini `git remote` must be SSH: `git@github.com:ethan-frost-xyz/founders-notes.git` |
| Merge conflict / not fast-forward | Fix on laptop, merge fix to `main`; never force-push without knowing mini state |

Until webhook works, **`/sync`** on Telegram is your pull fallback (bot idle only).

### 3. `/restart` sent but bot never comes back (~30s+)

Restart is real (process exit + launchd `KeepAlive`). Silence usually means **crash on startup** — bad code on disk, not a “fake” button.

1. **Laptop:** revert or fix-forward on `main`.
2. **Mini:** get fix on disk (`/sync` or wait for webhook).
3. **Mini Terminal** (SSH or at desk): run [status & restart block](mac-mini-operator-setup.md#mac-mini--status--restart-paste-in-terminal).
4. Read **`~/Library/Logs/founders-telegram/bot.stderr.log`** — last lines show import/syntax errors.

Restart alone does **not** fix bad code; you need a good commit on `main` first.

### 4. `409 Conflict` in logs or Telegram feels “stuck”

Two pollers are using the same bot token.

1. On mini: `services/telegram/deploy/stop-bot.sh`
2. Start **only one**: `deploy/restart-bot.sh` **or** one foreground `python -m bot` — never both.
3. Never run production `python -m bot` on the **laptop** while mini is polling.

### 5. “Another op is already running”

`/sync`, `/pull`, `/reindex` share a lock. Wait for the current op to finish, or avoid starting ops during a long Librarian turn.

`/restart` does not need the ops lock but **will** kill an in-progress Janitor session (in-memory state is lost).

### 6. Bad merge shipped to `main`

1. **Laptop:** revert PR or merge fix on GitHub.
2. **Mini:** webhook or **`/sync`** to get good tree.
3. **`/restart`** (or restart block if bot won’t stay up).

### 7. You need the mini but you’re not at the keyboard

| Need | From phone | From SSH (e.g. Tailscale) |
|------|------------|---------------------------|
| Pull + reindex | `/sync` when idle | `sync-and-index.sh` |
| Reload bot code | `/restart` | `deploy/restart-bot.sh` |
| Read crash reason | — | `tail -30 ~/Library/Logs/founders-telegram/bot.stderr.log` |
| Fix webhook | — | [mac-mini-operator-setup.md](mac-mini-operator-setup.md) restart block |

---

## What `/restart` is and isn’t

**Is:** Exit the bot process; launchd starts a new one that re-imports Python from `VAULT_ROOT`.

**Is not:** `git pull`, dependency install, or webhook repair. Do pull first (webhook or `/sync`), then restart.

**Works when:** `com.founders.telegram.bot` is loaded under launchd (normal production). If launchd isn’t installed, use `restart-bot.sh` on the mini or fix install per [services/telegram/README.md](../services/telegram/README.md).

---

## Local vs production testing

| Stage | Tool | Proves |
|-------|------|--------|
| Before merge | `pytest`, mock harness (`--stub-llm`) | Handlers, Janitor FSM, routing |
| After merge | Telegram on mini after **pull + restart** | Real Bot API, production env, full stack |

The harness **cannot** test restart (it would kill the mock process). Restart smoke is production-only: `/restart` → wait → `/start`.

---

## Related docs

- [laptop-development.md](laptop-development.md) — one-time laptop setup, CI parity
- [mac-mini-operator-setup.md](mac-mini-operator-setup.md) — paths, restart paste block, webhook verify
- [telegram-mock-harness.md](telegram-mock-harness.md) — pre-merge bot testing
- [manual-operations.md](manual-operations.md) — when to reindex (content / search)
