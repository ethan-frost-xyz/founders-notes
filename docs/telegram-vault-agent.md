# Telegram vault agent

Short overview for coding agents. **Master index:** [`.cursor/plans/telegram_rag_bot_v0.plan.md`](../.cursor/plans/telegram_rag_bot_v0.plan.md) (decisions + shared contracts). **v0 (SP1–SP4)** shipped on `main` (PR #3); archived sub-plans below. Follow-ups: see [`potential-ideas.md`](../potential-ideas.md).

| SP | Plan (archived) |
|----|------|
| 1 | [telegram_vault_sp1_tools.plan.md](../.cursor/plans/archive/telegram_vault_sp1_tools.plan.md) |
| 2 | [telegram_vault_sp2_agent.plan.md](../.cursor/plans/archive/telegram_vault_sp2_agent.plan.md) |
| 3 | [telegram_vault_sp3_telegram.plan.md](../.cursor/plans/archive/telegram_vault_sp3_telegram.plan.md) |
| 4 | [telegram_vault_sp4_ops.plan.md](../.cursor/plans/archive/telegram_vault_sp4_ops.plan.md) |

Product is a **tool-calling vault agent**, not naive single-shot RAG.

## Product

- Private Telegram bot on an always-on **Mac mini** (polling), solo user via `TELEGRAM_ALLOWED_USER_IDS`.
- **Librarian:** study-notes voice — synthesized insights + verbatim quotes + `[ep-NNNN]` citations — not ranked excerpt dumps.
- **Janitor:** daily notes ritual in the same bot — see [janitor.md](janitor.md).

## Architecture

- **OpenRouter agent** (`TELEGRAM_CHAT_MODEL`) with tool calling (`max_steps` ~5).
- Retrieval lives **inside tools** (`search_vault_parent`, `search_transcript`, `load_episode`, `list_episode_ids`) backed by `catalog/chunks.jsonl` and **parent-tier** hybrid keyword + embeddings (`catalog/embeddings.npy`, gitignored).
- **`/web <query>` only** for external search (`web_search` tool); normal messages must not silently mix web into vault answers.
- Librarian corpus = **studied episodes only** (timestamp bullets in `.notes.md`); un-listened episodes return no parent-tier hits.

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
| `/web <query>` | One turn with `allow_web=true` |
| `/janitor` | Enter Janitor — paste bullets → clean → expand → promote |
| `/librarian` | Exit Janitor back to Q&A |
| `/cancel` | Cancel Janitor workflow |

**Janitor:** mode-switched workflow (LLM-first paste clean, file, expand subprocess, promote, reindex). Full guide: [janitor.md](janitor.md). Runbook: [services/telegram/README.md](../services/telegram/README.md).

**Index sync (v0):** manual or cron `sync-and-index.sh` (`git pull` + `ingestion/lib/reindex_vault.py`). Install cron on Mac mini: `services/telegram/deploy/install-cron.sh`. GitHub webhook deferred — [`potential-ideas.md`](../potential-ideas.md).

After expanded promote on the Mac mini (or any host running the bot), run the same index rebuild so parent-tier chunks include **Quote** / **Key takeaway** sections. See [expanded-backfill.md](expanded-backfill.md).

## Implementation status

| SP | Status | Plan |
|----|--------|------|
| 1–4 | Shipped on `main` (PR #3) | [archive/sp1_tools … sp4_ops](../.cursor/plans/archive/) |
| Janitor MVP | Shipped | [janitor.md](janitor.md) |
| 5+ | Deferred | [potential-ideas.md](../potential-ideas.md) |

Runbook and env: [`services/telegram/README.md`](../services/telegram/README.md).

## Embeddings vs AGENTS.md

Repo-wide rule: do **not** add a general-purpose vector DB until grep + chunk search + agent tools fail your queries. The Telegram embed index is **scoped to parent chunks only** (posts, notes, expanded) inside `search_vault_parent`.

## Related

- [telegram-mock-harness.md](telegram-mock-harness.md) — local headless/REPL testing (no Bot API)
- [manual-operations.md](manual-operations.md) — Telegram vs `maintain.py`; [when to refresh the index](manual-operations.md#when-to-refresh-the-index)
- [janitor.md](janitor.md) — daily notes workflow; [model tuning playbook](janitor.md#model-tuning-playbook)
- [retrieval.md](retrieval.md) — chunk index + hybrid parent search
- [expanded-backfill.md](expanded-backfill.md) — corpus quality for parent tier
- [vault-agent-v0-checklist.md](vault-agent-v0-checklist.md) — verification
- [potential-ideas.md](../potential-ideas.md) — backlog
- Superseded background: [`.cursor/plans/archive/telegram_vault_bot.plan.md`](../.cursor/plans/archive/telegram_vault_bot.plan.md)
