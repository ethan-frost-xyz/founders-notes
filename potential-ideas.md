# Potential ideas

Parking lot for follow-ups out of scope for the shipped stack. **When implementing:** pull one cluster into a new focused `.cursor/plans/*.plan.md` (do not grow the Telegram master index).

Linked from: [`README.md`](README.md), [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md), [`services/telegram/README.md`](services/telegram/README.md).

## Decided / won't do (v0)

- **Section-filter slash commands** (`/transcript`, `/post`, `/notes`, `/expanded`) — use `load_episode` + corpus tiers instead.
- **Cloud Run / multi-host** — Mac mini is the host.
- **Sync file lock** — document “run `sync-and-index.sh` when idle”; not worth complexity at current scale.
- **Episode intent classifier** — superseded by shipped `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)); SP6 = prompt/tool copy tuning if tool storms return.
- **Repo-wide embeddings** — only after grep/chunk/agent tools fail real queries (gates in [`docs/retrieval.md`](docs/retrieval.md)).
- **Bulk backfill ep-0190+ posts** — intentional daily-ritual gap until posted on X; not import debt.

## Telegram / Librarian

- **SP5 — GitHub webhook** — push → `git pull` → `sync-and-index.sh`; exposure TBD (Tailscale preferred). Manual/cron sufficient until daily lag is painful. Related: **Janitor auto-reindex policy** (cron vs post-push webhook).
- **SP3.1 — `/web` provider** — wire Tavily or Brave once `WEB_SEARCH_API_KEY` is set; v0 stub returns `{"error":"not configured"}`.
- **SP6 — remaining** — optional LLM rerank on hybrid hits; extend retrieval scenarios toward MRR@8 as query set grows. Shipped lite (May 2026): tool copy, few-shot prompt, status messages, +2 retrieval scenarios, live harness preflight + `thematic_search.yaml`.
- **`/resume` auto-sync** — warn-only today; optional auto `sync-and-index.sh` on resume.

## Janitor

- **Streaming clean preview** — stream partial LLM output to Telegram during clean for perceived speed on long pastes.
- **Edit catalog title in frontmatter** — optional LLM pass to fix episode title in notes frontmatter (today title comes from catalog only; clean pass scrubs hook text).
- **Janitor separate process** — same bot (mode switch) vs second bot for multi-user (deferred).
- **Write audit log** — confirm destructive overwrites when re-filing notes.
- **BotFather persistent menu button** — optional; `/janitor` is in `setMyCommands` on bot start.
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).

## Retrieval and index

- **Post-promote chunk smoke** — automated check that promoted `.expanded.md` appears in parent-tier chunks (partially covered by `RUN_REBUILT_INDEX_SCENARIOS=1` tests).

## Ingestion and corpus

- **`expand_datapoints_llm.py --jobs N`** — parallel expand workers (today: manual parallel terminals only). See [`docs/expanded-backfill.md`](docs/expanded-backfill.md).
