# Telegram vault agent (planned)

Private on-the-go access to the Founders vault via a **tool-calling agent** — not a fixed embed→top-k→answer pipeline.

**Status:** SP1–SP3 on `feature/telegram-vault-bot` (vault tools, agent loop, Telegram polling). SP4 ops pending. **Git:** One focused commit per sub-plan; merge via PR (see master plan).

## Plans

| Doc | Role |
|-----|------|
| [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../../.cursor/plans/telegram_rag_bot_v0.plan.md) | **Master index** — decisions, shared contracts, success criteria |
| [`.cursor/plans/telegram_vault_sp1_tools.plan.md`](../../.cursor/plans/telegram_vault_sp1_tools.plan.md) | **SP1** — search + embeddings + vault tools (start here) |
| [`.cursor/plans/telegram_vault_sp2_agent.plan.md`](../../.cursor/plans/telegram_vault_sp2_agent.plan.md) | **SP2** — agent loop + prompt |
| [`.cursor/plans/telegram_vault_sp3_telegram.plan.md`](../../.cursor/plans/telegram_vault_sp3_telegram.plan.md) | **SP3** — Telegram + sessions |
| [`.cursor/plans/telegram_vault_sp4_ops.plan.md`](../../.cursor/plans/telegram_vault_sp4_ops.plan.md) | **SP4** — Mac mini deploy |
| [`.cursor/plans/archive/telegram_vault_bot.plan.md`](../../.cursor/plans/archive/telegram_vault_bot.plan.md) | Superseded background |
| [`docs/telegram-vault-agent.md`](../../docs/telegram-vault-agent.md) | Short overview for agents |

**One sub-plan per agent session** — do not load all plan files at once.

## Architecture (v0)

```text
Telegram (polling) → handlers → VaultAgent.run_turn()
                                    ↓
                              OpenRouter + tools (≤5 steps)
                                    ↓
                    search_vault_parent | search_transcript | load_episode | list_episode_ids
                                    ↓
              ingestion/lib/search_retrieval.py + catalog/chunks.jsonl [+ embeddings.npy parent tier]
```

- **UX:** Study-notes synthesis + verbatim quotes + `[ep-NNNN]` citations.
- **Sources (priority):** `.expanded.md` → raw notes → posts → transcripts (explicit tool only).
- **Web:** `/web <query>` sets `allow_web=true` for one turn; `web_search` disabled otherwise.
- **Sessions:** In-memory chat; `/clear`; `/newchat` → `catalog/telegram-sessions/*.jsonl`; `/resume`.

Target layout (see master plan): `services/telegram/bot/agent.py`, `bot/tools/vault.py`, `prompts/vault_agent.md`, `deploy/sync-and-index.sh`.

## Build order

1. **SP1** — `search_retrieval.py`, `build_embeddings.py` (parent-only), vault tool JSON backends + tests (no Telegram).
2. **SP2** — OpenRouter tool-calling loop + `vault_agent.md`.
3. **SP3** — `python-telegram-bot`, allowlist, session commands, `/web` gate (implemented).
4. **SP4** — Mac mini `launchd`, `~/.config/founders-telegram/env`, cron/manual `sync-and-index.sh`.

## Run locally (SP3)

```bash
pip install -r services/telegram/requirements.txt
# .env: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, OPENROUTER_*, TELEGRAM_CHAT_MODEL, VAULT_ROOT
cd services/telegram && python -m bot
```

## Prerequisites

- [docs/expanded-backfill.md](../../docs/expanded-backfill.md) — promote `.expanded.md` (not drafts) before expanded sections index well.
- [docs/retrieval.md](../../docs/retrieval.md) — `catalog/chunks.jsonl` via `ingestion/search/build_chunks.py`.

## Environment (v0)

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated numeric user ids (solo allowlist) |
| `VAULT_ROOT` | Path to git clone on Mac mini |
| `OPENROUTER_API_KEY` | Chat + embed API |
| `TELEGRAM_CHAT_MODEL` | Agent model (faster/cheaper than expand) |
| `OPENROUTER_EMBED_MODEL` | Parent-tier vectors for `search_vault_parent` |
| `WEB_SEARCH_API_KEY` | External search when `/web` provider is wired (SP3.1; v0 stub returns `not configured`) |

SP1+ implementation lives on `feature/telegram-vault-bot` — see master plan before adding `bot/` code.
