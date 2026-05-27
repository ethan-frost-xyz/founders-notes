# Telegram vault agent

Private on-the-go access to the Founders vault via a **tool-calling agent** — not a fixed embed→top-k→answer pipeline.

**Status:** SP1–SP4 shipped on `main` (PR #3). Mac mini deploy is operator setup — see install below.

**Reviewers:** [REVIEW.md](REVIEW.md) — commit map, risk areas, test commands.

## Plans

| Doc | Role |
|-----|------|
| [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../../.cursor/plans/telegram_rag_bot_v0.plan.md) | **Master index** — decisions, SP5/SP6 deferred |
| [`.cursor/plans/archive/telegram_vault_sp1_tools.plan.md`](../../.cursor/plans/archive/telegram_vault_sp1_tools.plan.md) | **SP1** (archived) — search + embeddings + vault tools |
| [`.cursor/plans/archive/telegram_vault_sp2_agent.plan.md`](../../.cursor/plans/archive/telegram_vault_sp2_agent.plan.md) | **SP2** (archived) — agent loop + prompt |
| [`.cursor/plans/archive/telegram_vault_sp3_telegram.plan.md`](../../.cursor/plans/archive/telegram_vault_sp3_telegram.plan.md) | **SP3** (archived) — Telegram + sessions |
| [`.cursor/plans/archive/telegram_vault_sp4_ops.plan.md`](../../.cursor/plans/archive/telegram_vault_sp4_ops.plan.md) | **SP4** (archived) — Mac mini deploy |
| [`docs/telegram-vault-agent.md`](../../docs/telegram-vault-agent.md) | Short overview for agents |

## Architecture

```text
Telegram (polling) → handlers → VaultAgent.run_turn()
                                    ↓
                              OpenRouter + tools (≤5 steps)
                                    ↓
                    search_vault_parent | search_transcript | load_episode | list_episode_ids
                                    ↓
              ingestion/lib/search_retrieval.py + catalog/chunks.jsonl [+ embeddings.npy]
```

## Mac mini install (SP4)

### 1. Clone and Python env

```bash
git clone <repo-url> ~/founders-notes
cd ~/founders-notes
python3 -m venv ingestion/.venv
ingestion/.venv/bin/pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
ingestion/.venv/bin/pip install -r services/telegram/requirements.txt
```

Use `ingestion/.venv/bin/python` for the bot and index scripts (recommended). If the venv is missing, `deploy/*.sh` falls back to `python3` on `PATH`.

### 2. Environment file

```bash
mkdir -p ~/.config/founders-telegram ~/Library/Logs/founders-telegram
cp services/telegram/deploy/env.example ~/.config/founders-telegram/env
chmod 600 ~/.config/founders-telegram/env
# Edit: VAULT_ROOT, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, OPENROUTER_*
```

Optional: `export FOUNDERS_TELEGRAM_ENV=~/.config/founders-telegram/env` if you use a non-default path.

### 3. Initial index

```bash
export $(grep -v '^#' ~/.config/founders-telegram/env | xargs)  # or source manually
services/telegram/deploy/sync-and-index.sh
```

Requires `OPENROUTER_API_KEY` and `OPENROUTER_EMBED_MODEL` for embeddings.

### 4. launchd (always-on bot)

Edit `services/telegram/deploy/com.founders.telegram.bot.plist` — replace placeholders:

| Placeholder | Example |
|-------------|---------|
| `REPLACE_WITH_VAULT_ROOT` | `/Users/you/founders-notes` |
| `REPLACE_WITH_HOME` | `/Users/you` |

```bash
chmod +x services/telegram/deploy/run-bot.sh services/telegram/deploy/sync-and-index.sh
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.founders.telegram.bot.plist 2>/dev/null || true
cp services/telegram/deploy/com.founders.telegram.bot.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.founders.telegram.bot.plist
launchctl enable gui/$(id -u)/com.founders.telegram.bot
```

Logs: `~/Library/Logs/founders-telegram/bot.stdout.log` and `bot.stderr.log`.

Unload: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.founders.telegram.bot.plist`

### 5. Cron index refresh (optional)

Run when the bot is **idle** (v0 has no file lock; avoid pulling during active turns):

```cron
0 4 * * * /Users/you/founders-notes/services/telegram/deploy/sync-and-index.sh >> ~/Library/Logs/founders-telegram/sync.log 2>&1
```

After promoting new `.expanded.md` files on another machine, run `sync-and-index.sh` on the Mac mini so parent-tier search includes them.

## Run locally (dev)

```bash
pip install -r services/telegram/requirements.txt
# Set env vars or copy deploy/env.example → .env at repo root
export VAULT_ROOT=$PWD
cd services/telegram && python -m bot
```

## Commands (Telegram)

| Command | Behavior |
|---------|----------|
| `/start` | Help + vault stats |
| `/clear` | Wipe in-memory thread |
| `/newchat` | Export → `catalog/telegram-sessions/*.jsonl`; reset |
| `/resume` | Load latest (or `/resume <fragment>`) |
| `/web <query>` | One turn with `allow_web=true` |
| Free text | Vault only (`allow_web=false`) |

## Environment

| Variable | Purpose |
|----------|---------|
| `VAULT_ROOT` | Git clone path |
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated numeric user ids |
| `OPENROUTER_API_KEY` | Chat + embed API |
| `TELEGRAM_CHAT_MODEL` | Agent model |
| `OPENROUTER_EMBED_MODEL` | Parent-tier embeddings |
| `TELEGRAM_MAX_STEPS` | Optional (default 5) |
| `WEB_SEARCH_API_KEY` | SP3.1 — `/web` provider (stub until wired) |

## Troubleshooting

| Issue | Check |
|-------|--------|
| Bot exits immediately | `bot.stderr.log`; env file sourced; `VAULT_ROOT` correct |
| `Unauthorized` in Telegram | Your numeric user id in `TELEGRAM_ALLOWED_USER_IDS` |
| Weak / no search hits | Run `sync-and-index.sh`; confirm `catalog/chunks.jsonl` updated |
| Embeddings errors | `OPENROUTER_EMBED_MODEL` + API key; run `build_embeddings.py` manually |
| Stale answers after git pull | Run sync when idle; `/resume` warns if index newer than session |

## Deferred (post-v0)

- **SP5:** GitHub push webhook → pull + reindex
- **SP3.1 / SP6:** Tavily or Brave for `/web`; tool tuning, status messages
