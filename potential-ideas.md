# Potential ideas

Parking lot for follow-ups that are out of scope for the current shipped stack. Pull items into a focused plan when you are ready to implement.

Linked from: [`README.md`](README.md), [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md), [`services/telegram/README.md`](services/telegram/README.md).

## Telegram / Librarian

- **SP5 — GitHub webhook** — push → `git pull` → `sync-and-index.sh`; exposure TBD (Tailscale preferred). Manual/cron is sufficient until daily lag is painful.
- **SP3.1 — `/web` provider** — wire Tavily or Brave once `WEB_SEARCH_API_KEY` is set; v0 stub returns `{"error":"not configured"}`.
- **SP6 — tool tuning** — improve tool descriptions + few-shot in system prompt; optional LLM rerank on top-20 hybrid hits; episode intent classifier before tool storms; Telegram “Searching notes…” status messages; golden query set (MRR@8).
- **Sync file lock** — avoid `sync-and-index.sh` during active agent turns (document “run when idle” today).
- **Section-filter slash commands** — `/transcript`, `/post`, `/notes`, `/expanded` filters (architecture may cover via `load_episode` + corpus filter instead).
- **Cloud Run / multi-host** — Mac mini is the chosen host for now.
- **`/resume` auto-sync** — warn-only today; optional auto `sync-and-index.sh` on resume.
- **Repo-wide embeddings** — only after ~400+ posts and grep/chunk/agent tools fail real queries (see `docs/retrieval.md`).

## Janitor

- **Streaming clean preview** — stream partial LLM output to Telegram during clean for perceived speed on long pastes.
- **Separate expand/promote models** — tune `OPENROUTER_MODEL` independently of `JANITOR_CLEAN_MODEL` (expand already separate; document tuning playbook in runbook).
- **Edit catalog title in frontmatter** — optional LLM pass to fix episode title in notes frontmatter (today title comes from catalog only; clean pass scrubs hook text).
- **Janitor auto-reindex policy** — promote already runs reindex on bot host; decide if nightly cron alone is enough vs explicit post-push webhook.
- **Janitor separate process** — same bot (mode switch) vs second bot for multi-user (deferred).
- **Write audit log** — confirm destructive overwrites when re-filing notes.
- **BotFather persistent menu button** — optional; `/janitor` is in `setMyCommands` on bot start.
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).

## Retrieval and index

- **LLM rerank on hybrid hits** — index is small after studied-episode filter; cost/complexity not justified yet.
- **Golden scenario / MRR@8 eval** — extend `vault_retrieval_scenarios.jsonl` when query set stabilizes.
- **Post-promote chunk smoke** — automated check that promoted `.expanded.md` appears in parent-tier chunks (partially covered by `RUN_REBUILT_INDEX_SCENARIOS=1` tests).

## Ingestion and corpus

- **`expand_datapoints_llm.py --jobs N`** — parallel expand workers (today: manual parallel terminals only). See `docs/expanded-backfill.md`.
- **Bulk backfill ep-0190+ posts** — intentional gap until episodes are posted on X; not an import bug.
