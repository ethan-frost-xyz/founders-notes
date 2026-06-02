---
name: Telegram Vault SP3 — Telegram + sessions
overview: "python-telegram-bot transport, allowlist, session commands, /web gate. Depends on SP2 VaultAgent."
todos:
  - id: bot-skeleton
    content: handlers.py, auth.py, sessions.py, config — thin layer over agent.run_turn()
    status: completed
  - id: commands
    content: /start /clear /newchat /resume /web — per command table
    status: completed
  - id: web-stub
    content: bot/tools/web.py returns not configured until WEB_SEARCH_API_KEY (SP3.1)
    status: completed
  - id: requirements
    content: services/telegram/requirements.txt with python-telegram-bot>=21 (separate from ingestion)
    status: completed
  - id: gitignore-sessions
    content: catalog/telegram-sessions/ gitignored
    status: completed
isProject: false
---

# SP3 — Telegram + sessions + `/web`

**Contracts (live docs):** [docs/telegram-vault-agent.md](../../../docs/telegram-vault-agent.md)  
**Requires:** [telegram_vault_sp2_agent.plan.md](telegram_vault_sp2_agent.plan.md)  
**Next:** [telegram_vault_sp4_ops.plan.md](telegram_vault_sp4_ops.plan.md)  
**Branch:** `feature/telegram-vault-bot` · **Commit:** SP3 only

## Agent handoff

Telegram is a **thin transport** over `VaultAgent.run_turn()`. Do **not** reimplement retrieval or the tool loop in handlers.

**Out of scope:** `launchd`, `sync-and-index.sh`, GitHub webhook (SP4/SP5).

## Goal

Polling bot on Mac mini (dev: local polling). Solo allowlist. In-memory sessions with export/resume.

## Deliverables

```
services/telegram/bot/
  __main__.py        # entrypoint: python -m services.telegram.bot
  handlers.py
  sessions.py
  auth.py
  config.py          # SP2 already created this — extend, do not duplicate
  tools/web.py       # promote SP2 inline stub to module; returns not configured until provider
```

`services/telegram/requirements.txt` — `python-telegram-bot>=21` (separate from `ingestion/requirements.txt`).

## Commands

| Command | Behavior |
|---------|----------|
| `/start` | Slash command help + vault stats (episode count, last indexed) |
| `/clear` | Wipe in-memory thread |
| `/newchat` | Export thread → `catalog/telegram-sessions/*.jsonl`; reset |
| `/resume` | Load session; warn if index newer than session (warn-only v0) |
| `/web <query>` | `VaultAgent.run_turn(..., allow_web=True)` **this turn only** |
| Free text | `allow_web=False` |

**Session export naming:** `catalog/telegram-sessions/{utc_iso}_{short_slug}.jsonl` (gitignore dir).

**`/resume` + stale index:** If `chunks.jsonl` / embeddings manifest mtime > session file → append warning to reply; no auto-sync in v0.

## `/web` v0

`web_search` returns `{"error":"not configured"}` until provider + `WEB_SEARCH_API_KEY` (SP3.1: Tavily or Brave).

## Auth

`TELEGRAM_ALLOWED_USER_IDS` — comma-separated numeric ids. Non-allowed users: reject before agent call.

## Environment

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | BotFather |
| `TELEGRAM_ALLOWED_USER_IDS` | Allowlist |
| `VAULT_ROOT` | Clone path |
| `OPENROUTER_API_KEY` | Chat + embed |
| `TELEGRAM_CHAT_MODEL` | Agent model |
| `OPENROUTER_EMBED_MODEL` | Parent-tier embeds |
| `WEB_SEARCH_API_KEY` | Later — `/web` provider |

## Library

`python-telegram-bot` v21+ in `services/telegram/requirements.txt`. Keep Telegram deps isolated from `ingestion/requirements.txt`.

## Verify before commit

| # | Check |
|---|--------|
| 1 | Non-allowed user id → no agent call |
| 2 | Free text → `allow_web=false` in agent |
| 3 | `/web foo` → `allow_web=true` for one turn |
| 4 | `/newchat` writes valid jsonl under `catalog/telegram-sessions/` |

```bash
cd ingestion && pytest -q && python pipeline/verify.py
```

## Commit message

`feat(telegram): SP3 bot handlers, sessions, and /web gate`
