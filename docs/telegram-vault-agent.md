# Telegram vault agent

Short overview for coding agents. **v0 (SP1–SP4)** shipped on `main` (PR #3); archived sub-plans below. Follow-ups: [`potential-ideas.md`](../potential-ideas.md). Implementation history: [`.cursor/plans/archive/`](../.cursor/plans/archive/).

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

- **OpenRouter agent** (Librarian model in `runtime.json`, `/setmodel librarian`) with tool calling (`max_steps` via `/setsteps`).
- Retrieval lives **inside tools** (`search_vault_parent`, `search_transcript`, `load_episode`, `list_episode_ids`) backed by `catalog/chunks.jsonl` and **parent-tier** hybrid keyword + embeddings (`catalog/embeddings.npy`, gitignored).
- **`/web <query>` only** for external search (`web_search` tool); normal messages must not silently mix web into vault answers.
- Librarian corpus = **studied episodes only** (timestamp bullets in `.notes.md`); un-listened episodes return no parent-tier hits.

## Source priority (agent policy)

1. `{folder}.expanded.md` (canonical; not `.expanded.draft.md`)
2. Raw `{folder}.notes.md` datapoints
3. `{folder}.post.md`
4. Transcripts — via `search_transcript` when dialogue grounding is needed

## Sessions and index

**BotFather menu (7 commands):** `/start`, `/janitor`, `/web`, `/settings`, `/sync`, `/newchat`, `/restart`. Power-user commands below still work when typed; they are omitted from the menu on purpose.

| Command | Behavior |
|---------|----------|
| `/start` | Catalog episode count, studied count (timestamp bullets), chunks index mtime |
| `/clear` | Wipe in-memory thread |
| `/newchat` | Export → `catalog/telegram-sessions/*.jsonl` (gitignored); reset |
| `/resume` | Reload exported session |
| `/web <query>` | One turn with `allow_web=true` |
| `/janitor` | Enter Janitor — paste bullets → clean → expand → promote |
| `/librarian` | Exit Janitor back to Q&A |
| `/cancel` | Exit Janitor (alias; same as **Exit Janitor** button) |
| `/settings` | Models, max_steps, **Ops** panel (sync / pull / reindex / restart) |
| `/setmodel` / `/resetmodel` | Per-role model overrides (`runtime.json`) |
| `/setsteps` / `/resetsteps` | Librarian tool-step limit |
| `/pull` | `git pull --ff-only` |
| `/reindex` | Rebuild chunks + embeddings |
| `/sync` | `/pull` then `/reindex` |
| `/restart` | Exit; launchd restarts bot |

**Janitor:** mode-switched workflow (LLM-first paste clean, file, expand subprocess, promote, reindex). Full guide: [janitor.md](janitor.md). Runbook: [services/telegram/README.md](../services/telegram/README.md).

**Index sync:** push to `main` → Mac mini GitHub webhook → `sync-and-index.sh`; or manual/cron/Telegram `/sync`. Cron: `install-cron.sh`. Webhook: `install-webhook.sh` + Tailscale Funnel — [services/telegram/README.md](../services/telegram/README.md#github-webhook-push-to-main).

After expanded promote on the Mac mini (or any host running the bot), run the same index rebuild so parent-tier chunks include **Quote** / **Key takeaway** sections. See [expanded-backfill.md](expanded-backfill.md).

## Implementation status

| SP | Status | Plan |
|----|--------|------|
| 1–4 | Shipped on `main` (PR #3) | [archive/sp1_tools … sp4_ops](../.cursor/plans/archive/) |
| Janitor MVP | Shipped | [janitor.md](janitor.md) |
| SP6-lite | Shipped (May 2026) | [potential-ideas.md](../potential-ideas.md) § Shipped |
| 5 (webhook) | Shipped | [telegram_ops_sync.plan.md](../.cursor/plans/archive/telegram_ops_sync.plan.md) |
| 6+ | Open — Next clusters | [potential-ideas.md](../potential-ideas.md) § Next |

Runbook and env: [`services/telegram/README.md`](../services/telegram/README.md).

## Embeddings vs AGENTS.md

Repo-wide rule: do **not** add a general-purpose vector DB until grep + chunk search + agent tools fail your queries. The Telegram embed index is **scoped to parent chunks only** (posts, notes, expanded) inside `search_vault_parent`.

## Related

- [telegram-mock-harness.md](telegram-mock-harness.md) — local headless/REPL testing (no Bot API)
- [laptop-development.md](laptop-development.md) — laptop clone, pytest, merge → webhook
- [mac-mini-operator-setup.md](mac-mini-operator-setup.md) — production Mac mini (daily ops, restart, troubleshooting)
- [manual-operations.md](manual-operations.md) — Telegram vs `maintain.py`; [when to refresh the index](manual-operations.md#when-to-refresh-the-index)
- [janitor.md](janitor.md) — daily notes workflow; [model tuning playbook](janitor.md#model-tuning-playbook)
- [retrieval.md](retrieval.md) — chunk index + hybrid parent search
- [expanded-backfill.md](expanded-backfill.md) — corpus quality for parent tier
- [vault-agent-v0-checklist.md](vault-agent-v0-checklist.md) — verification
- [potential-ideas.md](../potential-ideas.md) — backlog
- Superseded background: [`.cursor/plans/archive/telegram_vault_bot.plan.md`](../.cursor/plans/archive/telegram_vault_bot.plan.md)
