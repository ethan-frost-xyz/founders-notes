# Telegram vault agent

Short overview for coding agents. **Master index:** [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../.cursor/plans/telegram_rag_bot_v0.plan.md) (decisions + shared contracts). **v0 (SP1–SP4)** shipped on `main` (PR #3); archived sub-plans below. Follow-ups: SP5 webhook, SP6 tuning.

| SP | Plan (archived) |
|----|------|
| 1 | [telegram_vault_sp1_tools.plan.md](../.cursor/plans/archive/telegram_vault_sp1_tools.plan.md) |
| 2 | [telegram_vault_sp2_agent.plan.md](../.cursor/plans/archive/telegram_vault_sp2_agent.plan.md) |
| 3 | [telegram_vault_sp3_telegram.plan.md](../.cursor/plans/archive/telegram_vault_sp3_telegram.plan.md) |
| 4 | [telegram_vault_sp4_ops.plan.md](../.cursor/plans/archive/telegram_vault_sp4_ops.plan.md) |

Product is a **tool-calling vault agent**, not naive single-shot RAG.

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

## Implementation status

| SP | Status | Plan |
|----|--------|------|
| 1–4 | Shipped on `main` (PR #3) | [archive/sp1_tools … sp4_ops](../.cursor/plans/archive/) |
| 5 | Deferred | GitHub webhook → pull + reindex |
| 6 | Deferred | Tool copy, rerank, status UX |

Runbook and env: [`services/telegram/README.md`](../services/telegram/README.md).

## Embeddings vs AGENTS.md

Repo-wide rule: do **not** add a general-purpose vector DB until grep + chunk search + agent tools fail your queries. The Telegram embed index is **scoped to parent chunks only** (posts, notes, expanded) inside `search_vault_parent`.

## Related

- [retrieval.md](retrieval.md) — chunk index + hybrid parent search
- [expanded-backfill.md](expanded-backfill.md) — corpus quality for parent tier
- Superseded background: [`.cursor/plans/telegram_vault_bot.plan.md`](../.cursor/plans/telegram_vault_bot.plan.md)
