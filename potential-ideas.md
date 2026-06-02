# Potential ideas

Parking lot for follow-ups out of scope for the shipped stack. Organized as **Shipped (reference)**, **Next (pick one cluster → new plan)**, and **Decided / won't do**. When implementing, pull one cluster into a new focused `.cursor/plans/*.plan.md`. Contracts and decisions for the shipped Telegram agent live in [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md); removed master plan `telegram_rag_bot_v0` deferred items are consolidated below.

Linked from: [`README.md`](README.md), [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md), [`services/telegram/README.md`](services/telegram/README.md).

## Shipped (reference)

- **SP6-lite (May 2026)** — `services/telegram/bot/tool_status.py`, Telegram status labels in handlers/agent, prompt/tool copy, retrieval scenario additions, harness preflight + [`dev/scenarios/librarian/thematic_search.yaml`](dev/scenarios/librarian/thematic_search.yaml)
- **Mock harness (May 2026)** — `dev/mock_telegram_cli.py`, YAML scenarios (echo in CI; opt-in live via `RUN_LIVE_HARNESS=1`); guide [`docs/telegram-mock-harness.md`](docs/telegram-mock-harness.md); archived [`telegram_mock_harness_2296d9fc.plan.md`](.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md)
- **Index / ops (vault backlog)** — nightly cron (`install-cron.sh`), studied-corpus chunk filter, scenario tests, Janitor mode-switched bot
- **Episode resolution** — `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md))
- **`load_episode` disambiguation (Jun 2026)** — ambiguous refs return `candidates` from `list_episode_ids`; plan [`.cursor/plans/archive/telegram_librarian_quality.plan.md`](.cursor/plans/archive/telegram_librarian_quality.plan.md)
- **Librarian reply streaming (Jun 2026)** — optional synthesis token streaming via `/settings` → `stream_replies` in `runtime.json`; default on; same plan link
- **v0 checklist + Librarian copy (Jun 2026)** — un-listened examples use ep-0400 (James Dyson); aligned [`docs/vault-agent-v0-checklist.md`](docs/vault-agent-v0-checklist.md), [`vault_agent.md`](services/telegram/prompts/vault_agent.md), and test mocks
- **Post-promote chunk smoke (Jun 2026)** — promoted `.expanded.md` in parent-tier search via `test_v0_criterion_expanded_in_index` and retrieval JSONL scenarios when `RUN_REBUILT_INDEX_SCENARIOS=1`; see [`docs/vault-agent-v0-checklist.md`](docs/vault-agent-v0-checklist.md)
- **SP5 — GitHub webhook (May 2026)** — push to `main` → Tailscale Funnel → `github_webhook_server.py` → `sync-and-index.sh`; production ops [`docs/mac-mini-operator-setup.md`](docs/mac-mini-operator-setup.md); plans [`telegram_ops_sync.plan.md`](.cursor/plans/archive/telegram_ops_sync.plan.md), [`laptop_remote_hardening.plan.md`](.cursor/plans/archive/laptop_remote_hardening.plan.md)
- **Sync script runtime env (May 2026)** — `ingestion/lib/export_runtime_env.py` so cron/webhook reindex sees `embed_model` from `runtime.json` after slim env
- **Telegram UI overhaul (May 2026)** — curated 7-command BotFather menu; stats-only `/start` with studied count; Janitor **Exit Janitor** + overwrite confirm (`replace=True`); Ops panel under `/settings`; quieter ops/clean status — [`.cursor/plans/archive/telegram_ui_overhaul.plan.md`](.cursor/plans/archive/telegram_ui_overhaul.plan.md)
- **Janitor clean temperature (Jun 2026)** — Settings **Janitor temp** presets + `/setcleantemp` / `/resetcleantemp`; persisted in `runtime.json` (env fallback unchanged)
- **Librarian retrieval orchestrator** — studied-only parent index (`expanded` + `summary:episode`; no `notes:*` / `post:*`), `build_summaries.py`, `retrieval_orchestrator.py` + `rerank_llm.py`, agent = orchestrator + synthesis (optional `load_episode` / `list_episode_ids` / `web_search`); overview [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md); plan [`.cursor/plans/archive/librarian_retrieval_overhaul_7969c6d8.plan.md`](.cursor/plans/archive/librarian_retrieval_overhaul_7969c6d8.plan.md)
- **`vault_subprocess.py`** — shared `python_executable` / `tail_output` for `reindex_vault` and Janitor expand ([`ingestion/lib/vault_subprocess.py`](ingestion/lib/vault_subprocess.py))

## Next (pick one cluster → new plan)

Suggested plan filenames below — create the file under `.cursor/plans/` when you start work; archive under `.cursor/plans/archive/` when shipped.

### Ops / sync — `telegram_ops_followups.plan.md`

- **`/resume` auto-sync** — warn-only today; optional auto `sync-and-index.sh` on resume.
- **Path-filtered reindex** — code-only pushes still full reindex today (skip `build_chunks` / `build_embeddings` when diff touches no `content/`, `catalog/chunks.jsonl`, or index inputs).
- **Pull-only sync** — optional `git pull --ff-only` without reindex when webhook/cron sees a push with no vault-content paths (lighter than full `sync-and-index.sh`).
- **`/sync` handler integration tests** — deploy smoke covers webhook; no handler-level tests for Telegram `/sync`, `/pull`, `/reindex` yet.

### Web — `telegram_web_provider.plan.md`

- **SP3.1 — `/web` provider** — wire Tavily or Brave once `WEB_SEARCH_API_KEY` is set; [`web.py`](services/telegram/bot/tools/web.py) returns `not configured` (no key) or `provider not implemented` (key present).

### Harness / CI — `telegram_harness_ci.plan.md`

- **Live librarian deploy smoke** — document/run before Mac mini deploy: `python dev/mock_telegram_cli.py --suite librarian --live-only` (or `RUN_LIVE_HARNESS=1 pytest … -k live`) when keys + index preflight pass; record flakes here only if recurring.

### Agent / models — `telegram_agent_models.plan.md`

- **OpenRouter reasoning params** — wire optional `reasoning` / effort fields in [`agent.py`](services/telegram/bot/agent.py) when model supports them.
- **`max_steps` / `/setsteps` cleanup** — orchestrator path hardcodes 1–2 synthesis steps; runtime `max_steps` / `TELEGRAM_MAX_STEPS` are shown in `/settings` but not applied in [`agent.py`](services/telegram/bot/agent.py) `run_turn`. Rewire or remove misleading UX.

### Janitor UX — `janitor_ux.plan.md`

- **Streaming clean preview** — stream partial LLM output to Telegram during clean for perceived speed on long pastes.
- **Edit catalog title in frontmatter** — optional LLM pass to fix episode title in notes frontmatter (today title comes from catalog only; clean pass scrubs hook text).
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).
- **Janitor separate process** — same bot (mode switch) vs second bot for multi-user (deferred).
- **BotFather persistent menu button** — optional reply-keyboard shortcut; `/janitor` remains in the slim `setMyCommands` menu.

### Ingestion — `expand_parallel_workers.plan.md`

- **`expand_datapoints_llm.py --jobs N`** — parallel expand workers (today: manual parallel terminals only). See [`docs/expanded-backfill.md`](docs/expanded-backfill.md).
- **Remove `expand_llm.py` shim** — after all callers import `openrouter_client` / `expand_*` directly ([`expand_llm_split`](.cursor/plans/archive/expand_llm_split.plan.md) split shipped; shim still used by maintain, expand scripts, Janitor).

## Decided / won't do (v0)

- **Session export naming** — `catalog/telegram-sessions/{utc_iso}_{short_slug}.jsonl` (gitignored); implemented in [`sessions.py`](services/telegram/bot/sessions.py).
- **`TELEGRAM_MAX_STEPS` / runtime `max_steps`** — persisted for `/settings` and `/setsteps`; **orchestrator Librarian turns ignore it** (1–2 synthesis steps in `agent.py`). Cleanup → Agent/models cluster above.
- **`.expanded.draft.md` not indexed** — promote → `build_chunks` + `build_embeddings` before parent-tier search sees quotes.
- **Section-filter slash commands** (`/transcript`, `/post`, `/notes`, `/expanded`) — use `load_episode` + corpus tiers instead.
- **Cloud Run / multi-host** — Mac mini is the host.
- **Sync file lock (product)** — minimal `catalog/.sync-in-progress` in `sync-and-index.sh` is enough; no richer lock UX.
- **Replacing nightly cron** — keep cron + webhook + Telegram `/sync` fallback.
- **Episode intent classifier** — superseded by shipped `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)). Optional prompt/tool copy tuning if tool storms return — shipped SP6-lite May 2026.
- **Repo-wide embeddings** — only after grep/chunk/agent tools fail real queries (gates in [`docs/retrieval.md`](docs/retrieval.md)).
- **Bulk backfill ep-0190+ posts** — intentional daily-ritual gap until posted on X; not import debt.
