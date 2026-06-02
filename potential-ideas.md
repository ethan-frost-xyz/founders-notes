# Potential ideas

Parking lot for follow-ups out of scope for the shipped stack. Organized as **Shipped (reference)**, **Next (pick one cluster → new plan)**, and **Decided / won't do**. When implementing, pull one cluster into a new focused `.cursor/plans/*.plan.md`. Contracts and decisions for the shipped Telegram agent live in [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md); removed master plan `telegram_rag_bot_v0` deferred items are consolidated below.

Linked from: [`README.md`](README.md), [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md), [`services/telegram/README.md`](services/telegram/README.md).

## Shipped (reference)

- **SP6-lite (May 2026)** — `services/telegram/bot/tool_status.py`, Telegram status labels in handlers/agent, prompt/tool copy, retrieval scenario additions, harness preflight + [`dev/scenarios/librarian/thematic_search.yaml`](dev/scenarios/librarian/thematic_search.yaml)
- **Mock harness (May 2026)** — `dev/mock_telegram_cli.py`, YAML scenarios (echo in CI; opt-in live via `RUN_LIVE_HARNESS=1`); guide [`docs/telegram-mock-harness.md`](docs/telegram-mock-harness.md); archived [`telegram_mock_harness_2296d9fc.plan.md`](.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md)
- **Index / ops (vault backlog)** — nightly cron (`install-cron.sh`), studied-corpus chunk filter, scenario tests, Janitor mode-switched bot
- **Episode resolution** — `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)); fuzzy threshold tuning (D7) remains in Next
- **v0 checklist + Librarian copy (Jun 2026)** — un-listened examples use ep-0400 (James Dyson); aligned [`docs/vault-agent-v0-checklist.md`](docs/vault-agent-v0-checklist.md), [`vault_agent.md`](services/telegram/prompts/vault_agent.md), and test mocks
- **Post-promote chunk smoke (Jun 2026)** — promoted `.expanded.md` in parent-tier search via `test_v0_criterion_expanded_in_index` and retrieval JSONL scenarios when `RUN_REBUILT_INDEX_SCENARIOS=1`; see [`docs/vault-agent-v0-checklist.md`](docs/vault-agent-v0-checklist.md)
- **SP5 — GitHub webhook (May 2026)** — push to `main` → Tailscale Funnel → `github_webhook_server.py` → `sync-and-index.sh`; production ops [`docs/mac-mini-operator-setup.md`](docs/mac-mini-operator-setup.md); plans [`telegram_ops_sync.plan.md`](.cursor/plans/archive/telegram_ops_sync.plan.md), [`laptop_remote_hardening.plan.md`](.cursor/plans/archive/laptop_remote_hardening.plan.md)
- **Sync script runtime env (May 2026)** — `ingestion/lib/export_runtime_env.py` so cron/webhook reindex sees `embed_model` from `runtime.json` after slim env
- **Telegram UI overhaul (May 2026)** — curated 7-command BotFather menu; stats-only `/start` with studied count; Janitor **Exit Janitor** + overwrite confirm (`replace=True`); Ops panel under `/settings`; quieter ops/clean status — [`.cursor/plans/archive/telegram_ui_overhaul.plan.md`](.cursor/plans/archive/telegram_ui_overhaul.plan.md)
- **Janitor clean temperature (Jun 2026)** — Settings **Janitor temp** presets + `/setcleantemp` / `/resetcleantemp`; persisted in `runtime.json` (env fallback unchanged)

## Next (pick one cluster → new plan)

Suggested plan filenames below — create the file under `.cursor/plans/` when you start work; archive under `.cursor/plans/archive/` when shipped.

### Ops / sync — `telegram_ops_followups.plan.md`

- **`/resume` auto-sync** — warn-only today; optional auto `sync-and-index.sh` on resume.
- **Path-filtered reindex** — code-only pushes still full reindex today (skip `build_chunks` / `build_embeddings` when diff touches no `content/`, `catalog/chunks.jsonl`, or index inputs).
- **Pull-only sync** — optional `git pull --ff-only` without reindex when webhook/cron sees a push with no vault-content paths (lighter than full `sync-and-index.sh`).
- **`/sync` handler integration tests** — deploy smoke covers webhook; no handler-level tests for Telegram `/sync`, `/pull`, `/reindex` yet.

### Librarian quality — `telegram_librarian_quality.plan.md`

_From archived [`fix_bare_episode_refs`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md) deferred table + removed master plan SP6+._

- **`load_episode` disambiguation (D1)** — when `resolve_episode_ref` is ambiguous, return `{ "error": "...", "candidates": [...] }` from `list_episode_ids(..., limit=5)` so the model can pick in one turn.
- **Stricter tool schema (D2)** — document `load_episode.episode_id` as canonical `ep-NNNN` from `list_episode_ids`; prompt nudge to list before load; optional future `tool_choice` enforcement if model still skips list.
- **Stricter episode resolution (D3)** — limit fuzzy auto-pick; guest names through `list_episode_ids` + disambiguation (reduces wrong-episode risk, e.g. Henry Ford).
- **Shared episode ref helper (D5)** — digit / `ep-N` resolution in `ingestion/lib` for Librarian; Janitor keeps line-1 paste regex.
- **`tool_trace` resolved_from (D6)** — when `load_episode` uses fallback, record `resolved_from` in harness / exported session traces for debugging.
- **Fuzzy `resolve_episode_ref` tuning (D7)** — episode_number exact match, title boost for `#NNN`, re-evaluate thresholds with fixture queries.
- **`RUN_LIVE_HARNESS=1` pytest (D9)** — opt-in CI or local target for librarian YAML without `--stub-llm` when OpenRouter secrets present.
- **Ambiguous guest harness (D10)** — e.g. `ambiguous_guest.yaml` (Henry Ford → disambiguation, no wrong episode); [`episode_resolve.yaml`](dev/scenarios/librarian/episode_resolve.yaml) covers numbered NL only today.
- **LLM rerank** — optional rerank on hybrid hits; index is small after filter; revisit if quality gaps appear.
- **Scenarios / MRR@8** — extend retrieval scenarios toward MRR@8 as query set grows.
- **Librarian reply streaming (SSE)** — true token streaming to Telegram for Q&A turns (distinct from Janitor clean preview streaming).

### Web — `telegram_web_provider.plan.md`

- **SP3.1 — `/web` provider** — wire Tavily or Brave once `WEB_SEARCH_API_KEY` is set; v0 stub returns `{"error":"not configured"}`.

### Harness / CI — `telegram_harness_ci.plan.md`

- **Live librarian suite smoke** — before Mac mini deploy, run `python dev/mock_telegram_cli.py --suite librarian` without `--stub-llm` when keys present; record flakes in this file only if recurring.

### Agent / models — `telegram_agent_models.plan.md`

- **OpenRouter reasoning params** — wire optional `reasoning` / effort fields in [`agent.py`](services/telegram/bot/agent.py) when model supports them.

### Janitor UX — `janitor_ux.plan.md`

- **Streaming clean preview** — stream partial LLM output to Telegram during clean for perceived speed on long pastes.
- **Edit catalog title in frontmatter** — optional LLM pass to fix episode title in notes frontmatter (today title comes from catalog only; clean pass scrubs hook text).
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).
- **Janitor separate process** — same bot (mode switch) vs second bot for multi-user (deferred).
- **BotFather persistent menu button** — optional reply-keyboard shortcut; `/janitor` remains in the slim `setMyCommands` menu.

### Ingestion — `expand_parallel_workers.plan.md`

- **`expand_datapoints_llm.py --jobs N`** — parallel expand workers (today: manual parallel terminals only). See [`docs/expanded-backfill.md`](docs/expanded-backfill.md).
- **`vault_subprocess.py`** — dedupe `_python` / `_tail` helpers shared by reindex and Janitor expand subprocesses ([`expand_llm_split`](.cursor/plans/archive/expand_llm_split.plan.md) deferred).
- **Remove `expand_llm.py` shim** — after all callers import `openrouter_client` / `expand_*` directly.

## Decided / won't do (v0)

- **Session export naming** — `catalog/telegram-sessions/{utc_iso}_{short_slug}.jsonl` (gitignored).
- **`TELEGRAM_MAX_STEPS`** — optional env override; default 5 tool steps per Librarian turn.
- **`.expanded.draft.md` not indexed** — promote → `build_chunks` + `build_embeddings` before parent-tier search sees quotes.
- **Section-filter slash commands** (`/transcript`, `/post`, `/notes`, `/expanded`) — use `load_episode` + corpus tiers instead.
- **Cloud Run / multi-host** — Mac mini is the host.
- **Sync file lock (product)** — minimal `catalog/.sync-in-progress` in `sync-and-index.sh` is enough; no richer lock UX.
- **Replacing nightly cron** — keep cron + webhook + Telegram `/sync` fallback.
- **Episode intent classifier** — superseded by shipped `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)). Optional prompt/tool copy tuning if tool storms return — shipped SP6-lite May 2026.
- **Repo-wide embeddings** — only after grep/chunk/agent tools fail real queries (gates in [`docs/retrieval.md`](docs/retrieval.md)).
- **Bulk backfill ep-0190+ posts** — intentional daily-ritual gap until posted on X; not import debt.
