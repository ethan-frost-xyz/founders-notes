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
- **max_steps removal (Jun 2026)** — dropped misleading `/setsteps`, `TELEGRAM_MAX_STEPS`, and runtime `max_steps`; Librarian `run_turn` uses fixed 1–2 synthesis passes; plan [`.cursor/plans/archive/telegram_agent_models.plan.md`](.cursor/plans/archive/telegram_agent_models.plan.md)

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

### Agent / models — `telegram_agent_models_reasoning.plan.md`

- **OpenRouter reasoning params** — wire optional `reasoning.effort` in [`agent.py`](services/telegram/bot/agent.py) for Librarian synthesis only. **Not universal:** thinking-capable models only; `librarian_reasoning_effort` would be independent of `librarian_model` (changing model via `/setmodel` does not auto-clear effort). Pick product behavior first: opt-in docs, retry without reasoning on 4xx, env-only, or model allowlist. See [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

### Librarian latency — `librarian_retrieval_latency.plan.md`

High-level proposition from architecture review (Jun 2026): thematic Librarian turns feel slow **before any answer text** because retrieval is a **fully serial, blocking pipeline** (expand → embed + hybrid search ×5 → rerank, optional second rerank on transcript fallback) that must finish before synthesis can stream. That is separate from “one API call” — the vault still requires select-then-generate; the cost is **stacked remote steps + no overlap with synthesis**.

**Operational win (no code):** On the Mac mini bot host, set `retrieval_model` to a fast Groq-routed slug (e.g. `openai/gpt-oss-20b::Groq`, same family as Janitor clean) via `/setmodel retrieval …` or `~/.config/founders-telegram/runtime.json`; keep `librarian_model` on a stronger model for synthesis only. Laptop `runtime.json` does not affect production; models are not in git ([`docs/mac-mini-operator-setup.md`](docs/mac-mini-operator-setup.md), [`docs/remote-product-workflow.md`](docs/remote-product-workflow.md)). Shipped role: `retrieval_model` drives **both** expand and rerank; if unset, both fall back to `librarian_model` (common misconfig).

**Code follow-ups (pick by impact):**

- **Split expand vs rerank models** — two runtime keys so a weak/fast model can own one step without the other (expand vs rerank trade different quality risks).
- **Overlap embed with expand** — start batched `embed_queries` as soon as variants exist (or parallelize where safe).
- **Cheaper rerank path** — cap pool below 40, skip LLM rerank when hybrid/RRF confidence is high, or trust RRF-only on `follow_up` intent (today follow-ups still run full retrieval).
- **Local retrieval hygiene** — cache `load_chunks()` across the five variant searches (re-read JSONL each pass today).
- **Default prod retrieval slug** — seed or document Groq retrieval on mini install so new hosts do not run expand+rerank on the synthesis model by default.

See [`docs/retrieval.md`](docs/retrieval.md), [`docs/janitor.md`](docs/janitor.md) (example model matrix).

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
- **`.expanded.draft.md` not indexed** — promote → `build_chunks` + `build_embeddings` before parent-tier search sees quotes.
- **Section-filter slash commands** (`/transcript`, `/post`, `/notes`, `/expanded`) — use `load_episode` + corpus tiers instead.
- **Cloud Run / multi-host** — Mac mini is the host.
- **Sync file lock (product)** — minimal `catalog/.sync-in-progress` in `sync-and-index.sh` is enough; no richer lock UX.
- **Replacing nightly cron** — keep cron + webhook + Telegram `/sync` fallback.
- **Episode intent classifier** — superseded by shipped `resolve_episode_ref` + `load_episode` fallback ([`archive/fix_bare_episode_refs_4f718a49.plan.md`](.cursor/plans/archive/fix_bare_episode_refs_4f718a49.plan.md)). Optional prompt/tool copy tuning if tool storms return — shipped SP6-lite May 2026.
- **Repo-wide embeddings** — only after grep/chunk/agent tools fail real queries (gates in [`docs/retrieval.md`](docs/retrieval.md)).
- **Bulk backfill ep-0190+ posts** — intentional daily-ritual gap until posted on X; not import debt.
