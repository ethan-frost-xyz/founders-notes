# Telegram vault agent (planned)

Short overview for coding agents. **Implementation:** [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../.cursor/plans/telegram_rag_bot_v0.plan.md) (filename kept for history; product is a **tool-calling vault agent**, not naive single-shot RAG).

## Product

- Private Telegram bot on an always-on **Mac mini** (polling), solo user via `TELEGRAM_ALLOWED_USER_IDS`.
- Answers in **study-notes voice**: synthesized insights + verbatim quotes + `[ep-NNNN]` citations — not ranked excerpt dumps.

## Architecture

- **OpenRouter agent** (`TELEGRAM_CHAT_MODEL`) with tool calling (`max_steps` ~5).
- Retrieval lives **inside tools** (`search_vault_parent`, `search_transcript`, `load_episode`, `list_episode_ids`) backed by `catalog/chunks.jsonl` and **parent-tier** hybrid keyword + embeddings (`catalog/embeddings.npy`, gitignored).
- **`/web <query>` only** for external search (`web_search` tool); normal messages must not silently mix web into vault answers.

## Source priority (agent policy)

1. `{folder}.expanded.md` (canonical; not `.expanded.draft.md`)
2. Raw `{folder}.notes.md` datapoints
3. `{folder}.post.md`
4. Transcripts — via `search_transcript` when dialogue grounding is needed

## Sessions and index

| Command | Behavior |
|---------|----------|
| `/clear` | Wipe in-memory thread |
| `/newchat` | Export → `catalog/telegram-sessions/*.jsonl` (gitignored); reset |
| `/resume` | Reload exported session |

**Index sync (v0):** manual or cron `sync-and-index.sh` (`git pull` + `build_chunks.py` + `build_embeddings.py`). GitHub webhook deferred.

After expanded promote on the Mac mini (or any host running the bot), run the same index rebuild so parent-tier chunks include **Quote** / **Key takeaway** sections. See [expanded-backfill.md](expanded-backfill.md).

## Build order and branch

All implementation on **`feature/telegram-vault-bot`** off `main`:

1. SP1 — vault tools + `search_retrieval` + `build_embeddings`
2. SP2 — agent loop + `vault_agent.md` prompt
3. SP3 — Telegram transport, allowlist, sessions, `/web` gate
4. SP4 — Mac mini `launchd` + ops

Stub and env reference: [`services/telegram/README.md`](../services/telegram/README.md).

## Embeddings vs AGENTS.md

Repo-wide rule: do **not** add a general-purpose vector DB until grep + chunk search + agent tools fail your queries. The Telegram embed index is **scoped to parent chunks only** (posts, notes, expanded) inside `search_vault_parent`.

## Related

- [retrieval.md](retrieval.md) — chunk index today; agent tools next
- [expanded-backfill.md](expanded-backfill.md) — corpus quality for parent tier
- Superseded background: [`.cursor/plans/telegram_vault_bot.plan.md`](../.cursor/plans/telegram_vault_bot.plan.md)
