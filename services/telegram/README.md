# Telegram vault agent

Private on-the-go access to the Founders vault via a **tool-calling agent** — not a fixed embed→top-k→answer pipeline.

**Status:** SP1–SP4 shipped on `main` (PR #3). Mac mini deploy is operator setup — see install below.

**Reviewers:** [REVIEW.md](REVIEW.md) — commit map, risk areas, test commands.

**Docs:** [`docs/telegram-vault-agent.md`](../../docs/telegram-vault-agent.md) (overview) · [`docs/janitor.md`](../../docs/janitor.md) (daily notes workflow) · [`docs/manual-operations.md`](../../docs/manual-operations.md) (Telegram vs `maintain.py`) · [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../../.cursor/plans/telegram_rag_bot_v0.plan.md) (master index) · [`potential-ideas.md`](../../potential-ideas.md) (deferred backlog)

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

### 2. Environment files (two locations)

The Mac mini needs **both**:

| File | Purpose |
|------|---------|
| `~/.config/founders-telegram/env` | Bot runtime (launchd, sync scripts) — copy from `deploy/env.example` |
| `{VAULT_ROOT}/.env` | Ingestion (Colossus, X API); expand subprocess also `load_dotenv` on repo root |

```bash
mkdir -p ~/.config/founders-telegram ~/Library/Logs/founders-telegram
cp services/telegram/deploy/env.example ~/.config/founders-telegram/env
chmod 600 ~/.config/founders-telegram/env
cp .env.example .env   # in repo root — edit Colossus/X/OpenRouter as needed
# Edit Telegram env: VAULT_ROOT, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, OPENROUTER_*
```

Quick view:

```bash
cat ~/.config/founders-telegram/env    # bot runtime
cat "$VAULT_ROOT/.env"                 # ingestion / expand (set VAULT_ROOT first)
```

Optional: `export FOUNDERS_TELEGRAM_ENV=~/.config/founders-telegram/env` if you use a non-default path.

### 3. Initial index

```bash
export $(grep -v '^#' ~/.config/founders-telegram/env | xargs)  # or source manually
services/telegram/deploy/sync-and-index.sh
```

After `git pull`, the script runs [`ingestion/lib/reindex_vault.py`](../../ingestion/lib/reindex_vault.py) (chunks + embeddings). Requires `OPENROUTER_API_KEY` and `OPENROUTER_EMBED_MODEL` (any OpenRouter embedding slug) for the embedding step.

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

Run when the bot is **idle** (v0 has no file lock; avoid reindex during active turns). Full matrix (laptop push, promote failure, `/resume`): [`docs/manual-operations.md`](../../docs/manual-operations.md#when-to-refresh-the-index).

```bash
chmod +x services/telegram/deploy/install-cron.sh
services/telegram/deploy/install-cron.sh
```

Or add manually:

```cron
0 4 * * * /Users/you/founders-notes/services/telegram/deploy/sync-and-index.sh >> ~/Library/Logs/founders-telegram/sync.log 2>&1
```

After promoting new `.expanded.md` files on another machine, run `sync-and-index.sh` on the Mac mini so parent-tier search includes them.

## Run locally (dev)

Telegram secrets live in **`~/.config/founders-telegram/env`**, not the repo root `.env` (that file is for ingestion/X/Colossus). Copy `deploy/env.example` there first.

**Only one poller at a time** — Telegram returns `409 Conflict` if launchd and a terminal bot both run. The bot acquires `~/Library/Logs/founders-telegram/bot.poll.lock`; a second start exits immediately.

```bash
# Mac mini: use launchd (recommended)
services/telegram/deploy/restart-bot.sh

# Foreground dev (stops launchd + any stray pollers first)
services/telegram/deploy/stop-bot.sh
set -a && source ~/.config/founders-telegram/env && set +a
cd services/telegram && ../../ingestion/.venv/bin/python -m bot
```

## Local harness (no Bot API)

Exercise Librarian and Janitor handlers without Telegram or a bot token.

```bash
# From repo root — CI parity (echo)
pytest tests/test_harness_scenarios.py -q

# Interactive REPL (echo)
python dev/mock_telegram_cli.py --stub-llm --debug

# Live Librarian smoke (~7 min; auto-loads ~/.config/founders-telegram/env)
python dev/mock_telegram_cli.py --suite librarian --live-only -v
```

`--suite` and `--scenario` run YAML flows directly (no `--run-scenarios` needed). Janitor scenarios write to `dev/logs/sandbox/` only — not `content/notes/`. Full guide: [`docs/telegram-mock-harness.md`](../../docs/telegram-mock-harness.md). Scenario index: [`dev/scenarios/README.md`](../../dev/scenarios/README.md).

## Janitor (daily notes)

Mode-switched workflow in the same bot: `/janitor` → paste bullets → LLM clean preview → approve → file `.notes.md` → expand → promote → reindex. Full guide: [`docs/janitor.md`](../../docs/janitor.md).

Requires `JANITOR_CLEAN_MODEL` in `~/.config/founders-telegram/env`. Expand uses `OPENROUTER_MODEL` (Telegram env and/or `{VAULT_ROOT}/.env`).

**Model tuning:** clean, expand, and Librarian chat use separate env vars — when to change each, example stacks, restart steps: [`docs/janitor.md`](../../docs/janitor.md#model-tuning-playbook).

## Commands (Telegram)

| Command | Behavior |
|---------|----------|
| `/start` | Help + vault stats |
| `/clear` | Wipe in-memory thread |
| `/newchat` | Export → `catalog/telegram-sessions/*.jsonl`; reset |
| `/resume` | Load latest (or `/resume <fragment>`) |
| `/web <query>` | One turn with `allow_web=true` |
| `/janitor` | Notes ingest → expand → promote workflow |
| `/librarian` | Exit Janitor back to Q&A |
| `/cancel` | Cancel Janitor workflow |
| Free text | Vault only (`allow_web=false`); in Janitor mode, follows notes workflow |

## Environment variables

Set bot vars in `~/.config/founders-telegram/env`. Ensure `{VAULT_ROOT}/.env` has `OPENROUTER_API_KEY` (and optionally `OPENROUTER_MODEL`) for Janitor expand if not duplicated in the Telegram env.

| Variable | Purpose |
|----------|---------|
| `VAULT_ROOT` | Git clone path (repo root; resolved via [`ingestion/_bootstrap.py`](../../ingestion/_bootstrap.py) `resolve_vault_root`) |
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated numeric user ids |
| `OPENROUTER_API_KEY` | Chat + embed API |
| `TELEGRAM_CHAT_MODEL` | Librarian agent model |
| `JANITOR_CLEAN_MODEL` | Janitor **paste clean** (required for `/janitor`; LLM-first, e.g. `groq/llama-3.1-8b-instant`) |
| `JANITOR_CLEAN_TEMPERATURE` | Optional (default `0.2`) |
| `OPENROUTER_MODEL` | Janitor **expand** subprocess (`expand_datapoints_llm.py`) |
| `OPENROUTER_EMBED_MODEL` | Parent-tier embeddings (any OpenRouter embedding slug) |
| `TELEGRAM_MAX_STEPS` | Optional (default 5) |
| `WEB_SEARCH_API_KEY` | SP3.1 — `/web` provider (stub until wired) |

## Troubleshooting

| Issue | Check |
|-------|--------|
| `409 Conflict` / two getUpdates | Run `deploy/stop-bot.sh` then **either** `restart-bot.sh` **or** one terminal `python -m bot` — not both |
| Bot exits immediately | `bot.stderr.log`; env file sourced; `VAULT_ROOT` correct |
| `Unauthorized` in Telegram | Your numeric user id in `TELEGRAM_ALLOWED_USER_IDS` |
| Weak / no search hits | Run `sync-and-index.sh`; confirm `catalog/chunks.jsonl` updated |
| Embeddings errors | `OPENROUTER_EMBED_MODEL` + API key; run `build_embeddings.py` manually |
| Stale answers after git pull | Run sync when idle; `/resume` warns if index newer than session |

## Deferred (post-v0)

See [`potential-ideas.md`](../../potential-ideas.md) — SP6-lite shipped; SP5+, rerank, MRR@8, Janitor UX → **Next** clusters.
