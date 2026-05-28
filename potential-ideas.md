# Potential ideas

Parking lot for follow-ups out of scope for the shipped stack. Organized as **Shipped (reference)**, **Next (pick one cluster → new plan)**, and **Decided / won't do**. When implementing, pull one cluster into a new focused `.cursor/plans/*.plan.md` (do not grow the Telegram master index).

Linked from: [`README.md`](README.md), [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md), [`services/telegram/README.md`](services/telegram/README.md).

## Shipped (reference)

- **SP6-lite (May 2026)** — `services/telegram/bot/tool_status.py`, Telegram status labels in handlers/agent, prompt/tool copy, retrieval scenario additions, harness preflight + [`dev/scenarios/librarian/thematic_search.yaml`](dev/scenarios/librarian/thematic_search.yaml)
- **Index / ops (vault backlog)** — nightly cron (`install-cron.sh`), studied-corpus chunk filter, scenario tests, Janitor mode-switched bot
- **Episode resolution** — `resolve_episode_ref` ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)); fuzzy threshold tuning (D7) **not** shipped — see Librarian quality below

## Next (pick one cluster → new plan)

### Ops / sync — `telegram_ops_sync.plan.md`

- **SP5 — GitHub webhook** — push → `git pull` → `sync-and-index.sh`; exposure TBD (Tailscale preferred). Manual/cron sufficient until daily lag is painful.
- **`/resume` auto-sync** — warn-only today; optional auto `sync-and-index.sh` on resume.
- **Janitor auto-reindex policy** — cron vs post-push webhook (related to SP5).

### Librarian quality — `telegram_librarian_quality.plan.md`

- **LLM rerank** — optional rerank on hybrid hits; index is small after filter; revisit if quality gaps appear.
- **Scenarios / MRR@8** — extend retrieval scenarios toward MRR@8 as query set grows.
- **Post-promote chunk smoke** — automated check that promoted `.expanded.md` appears in parent-tier chunks (partially covered by `RUN_REBUILT_INDEX_SCENARIOS=1` tests).
- **Fuzzy `resolve_episode_ref` tuning (D7)** — episode_number exact match, title boost for `#NNN`, re-evaluate thresholds with fixture queries.

### Web — `telegram_web_provider.plan.md`

- **SP3.1 — `/web` provider** — wire Tavily or Brave once `WEB_SEARCH_API_KEY` is set; v0 stub returns `{"error":"not configured"}`.

### Janitor UX — `janitor_ux.plan.md`

- **Streaming clean preview** — stream partial LLM output to Telegram during clean for perceived speed on long pastes.
- **Edit catalog title in frontmatter** — optional LLM pass to fix episode title in notes frontmatter (today title comes from catalog only; clean pass scrubs hook text).
- **Write audit log** — confirm destructive overwrites when re-filing notes.
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).
- **Janitor separate process** — same bot (mode switch) vs second bot for multi-user (deferred).
- **BotFather persistent menu button** — optional; `/janitor` is in `setMyCommands` on bot start.

### Ingestion — `expand_parallel_workers.plan.md`

- **`expand_datapoints_llm.py --jobs N`** — parallel expand workers (today: manual parallel terminals only). See [`docs/expanded-backfill.md`](docs/expanded-backfill.md).

## Decided / won't do (v0)

- **Section-filter slash commands** (`/transcript`, `/post`, `/notes`, `/expanded`) — use `load_episode` + corpus tiers instead.
- **Cloud Run / multi-host** — Mac mini is the host.
- **Sync file lock** — document “run `sync-and-index.sh` when idle”; not worth complexity at current scale.
- **Episode intent classifier** — superseded by shipped `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)). Optional prompt/tool copy tuning if tool storms return — shipped SP6-lite May 2026.
- **Repo-wide embeddings** — only after grep/chunk/agent tools fail real queries (gates in [`docs/retrieval.md`](docs/retrieval.md)).
- **Bulk backfill ep-0190+ posts** — intentional daily-ritual gap until posted on X; not import debt.
