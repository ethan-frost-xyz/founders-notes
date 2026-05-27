---
name: Telegram Vault SP3 — Telegram + sessions
overview: "python-telegram-bot transport, allowlist, session commands, /web gate. Depends on SP2 VaultAgent."
todos:
  - id: bot-skeleton
    content: handlers.py, auth.py, sessions.py, config — thin layer over agent.run_turn()
    status: pending
  - id: commands
    content: /start /clear /newchat /resume /web — per command table
    status: pending
  - id: web-stub
    content: bot/tools/web.py returns not configured until WEB_SEARCH_API_KEY (SP3.1)
    status: pending
  - id: requirements
    content: python-telegram-bot>=21 in services/telegram/requirements.txt or ingestion/requirements.txt
    status: pending
  - id: gitignore-sessions
    content: catalog/telegram-sessions/ gitignored
    status: pending
isProject: false
---

# SP3 — Telegram + sessions + `/web`

**Master (contracts only):** [telegram_rag_bot_v0.plan.md](telegram_rag_bot_v0.plan.md)  
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
  handlers.py
  sessions.py
  auth.py
  config.py          # may extend SP2 config
  tools/web.py       # stub until provider
```

Entrypoint: `python -m` or `services/telegram/bot/__main__.py` (choose one convention; document in README).

## Commands

| Command | Behavior |
|---------|----------|
| `/start` | Help, index stats, tool list |
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

`python-telegram-bot` v21+.

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
