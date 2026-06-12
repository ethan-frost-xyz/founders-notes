# Potential ideas

Deferred work only. Shipped behavior lives in the codebase and [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md) (runbooks: [`services/telegram/README.md`](services/telegram/README.md)). Historical plans: [`.cursor/plans/archive/legacy/`](.cursor/plans/archive/legacy/) (deep archive).

**Living detail:** Librarian synthesis/evidence quality — [`.cursor/plans/librarian_output_quality.md`](.cursor/plans/librarian_output_quality.md). Manual content gaps — [`catalog/import-review.md`](catalog/import-review.md).

Pick one cluster → new `.cursor/plans/*.plan.md` → archive the plan when done → remove the cluster from this file (do not add a changelog section here).

## Telegram

### Ops / sync (recommended next)

**Defer:** Pull-only / path-filtered reindex on webhook when *all* changed paths match a strict allowlist (`docs/`, `tests/`, `services/telegram/`, `.cursor/`, root markdown); anything under `content/`, `catalog/`, or `ingestion/search/` → full reindex. False negative → stale search until `/sync`. Nightly cron stays full sync. Today [`github_webhook_server.py`](services/telegram/deploy/github_webhook_server.py) always runs [`sync-and-index.sh`](services/telegram/deploy/sync-and-index.sh) (full pull + `reindex_vault.py`). Bundle in one plan only if code-only `main` pushes hurt.

- **Richer sync / push lock UX** — Today overlapping webhook/cron sync skips cleanly via `catalog/.sync-in-progress` (no user-facing status). See [`services/telegram/README.md`](services/telegram/README.md) (sync locks) and [`docs/operations.md`](docs/operations.md#when-to-refresh).

### Harness / CI

- **Live librarian deploy smoke** — Before Mac mini deploy: `python dev/mock_telegram_cli.py --preflight` then `--suite librarian --live-only -v` (15 live scenarios, ~8–12 min OpenRouter; or `RUN_LIVE_HARNESS=1 pytest … -k live`). Preflight checks keys + local index; live runs auto-preflight when needed. See [`docs/telegram-mock-harness.md`](docs/telegram-mock-harness.md), [`docs/operations.md`](docs/operations.md#mac-mini--quick-test-ladder).
- **Live re-baseline (post lift B + lift 2)** — Re-run full suite on Mac mini; compare to [`dev/logs/runs/2026-06-09-librarian-live-suite-summary.json`](dev/logs/runs/2026-06-09-librarian-live-suite-summary.json). Playbook: [`dev/scenarios/librarian/RERUN-LIVE-SUITE.md`](dev/scenarios/librarian/RERUN-LIVE-SUITE.md). Skill: [`.cursor/skills/librarian-live-suite-loop/SKILL.md`](.cursor/skills/librarian-live-suite-loop/SKILL.md).
- **Agentic stress baseline (#12–15)** — `ood_decline`, `negative_constraints`, `verbatim_intent`, `tool_efficiency` have no baseline rows yet; capture after first green Mac mini run. Queue: [`RERUN-LIVE-SUITE.md`](dev/scenarios/librarian/RERUN-LIVE-SUITE.md#queue-15).
- **Janitor live harness** — Janitor scenarios are `llm: echo` only (CI-safe); optional live clean/expand smoke not built. Scenarios: [`dev/scenarios/janitor/`](dev/scenarios/janitor/).
- **Deploy / ops automated checks** — Pre-deploy gate beyond pytest (webhook, sync script, index freshness). Flagged in [`services/telegram/README.md`](services/telegram/README.md#deferred-post-v0); no spec yet.

### Agent / models

- **OpenRouter reasoning params** — Optional `reasoning.effort` in [`agent_core.py`](services/telegram/bot/agent_core.py) for Librarian synthesis only (thinking-capable models). `librarian_reasoning_effort` independent of `librarian_model`. Decide first: opt-in docs, retry without reasoning on 4xx, env-only, or model allowlist. [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
- **OpenRouter web / browsing provider** — External facts beyond the vault (if ever needed). Flagged in [`services/telegram/README.md`](services/telegram/README.md#deferred-post-v0); no spec yet.

### Librarian quality

Detail and priority order: [`.cursor/plans/librarian_output_quality.md`](.cursor/plans/librarian_output_quality.md).

- **`structured_embed_text` in vault evidence blocks** — Use in [`format_evidence_for_tool`](services/telegram/lib/evidence_format.py) (lift 3; index build already uses it in [`search_embeddings.py`](ingestion/lib/search_embeddings.py)).
- **`librarian_temperature` runtime key** — `/setmodel`-style control for synthesis temperature (Janitor has `janitor_clean_temperature` today).
- **Stream-preview sanitization** — `stream_replies` ships; streamed tokens may show raw markdown before [`reply_sanitize.py`](services/telegram/bot/reply_sanitize.py) runs on the final message.
- **Transcript vs vault evidence format** — Minor unification in [`evidence_format.py`](services/telegram/lib/evidence_format.py) / [`search_turn.py`](services/telegram/bot/search_turn.py).
- **`_meta` echoed in model replies** — Clearer evidence delimiter so synthesis does not repeat trace metadata.
- **Multi-turn evidence in history** — Optional compact evidence summary across turns (today only chat text persists).
- **Trace-aware thin evidence harness** — Optional assertion that thin-evidence turns reference `tool_trace` / cap behavior. Gap: [librarian_output_quality.md § Testing gaps](.cursor/plans/librarian_output_quality.md#testing-gaps-to-close).

### Librarian latency

Operational tuning (no code): fast `retrieval_model` on the Mac mini — [`docs/janitor.md`](docs/janitor.md#model-tuning-playbook), [`docs/retrieval.md`](docs/retrieval.md). Tap presets: `/setmodel` UI in [`model_presets.py`](services/telegram/bot/model_presets.py). Live harness baseline: `retrieval_model: deepseek/deepseek-v4-flash`, `librarian_model: deepseek/deepseek-v4-pro` ([`RERUN-LIVE-SUITE.md`](dev/scenarios/librarian/RERUN-LIVE-SUITE.md)).

**Retrieval baseline shipped** (orchestrator): batched variant embed (`embed_queries`), parallel per-variant hybrid search (`ThreadPoolExecutor` in [`orchestrator.py`](services/telegram/lib/retrieval/orchestrator.py)), `get_chunk_index` mtime cache, `EXPAND_VARIANTS_LIGHT` (2 variants) on `search_vault_many`. Separate runtime roles: `librarian_model` (synthesis), `retrieval_model` (orchestrator expand + rerank), `expand_model` (Janitor `expand_datapoints_llm` subprocess).

- **Split expand vs rerank models (orchestrator)** — `retrieval_model` still drives both expand and rerank inside `retrieve_core`; deferred: `rerank_model` independent of expand. Also listed under [What not to refactor yet](.cursor/plans/librarian_output_quality.md#what-not-to-refactor-yet).
- **Overlap embed with expand** — Pipeline is expand → embed; start batched `embed_queries` when variants exist (overlap wall time with expand LLM).
- **Cheaper rerank path** — Smaller pool, skip LLM rerank on high RRF confidence, or RRF-only on light / follow-up turns (`search_vault_many` still reranks today).
- **Shared ChunkIndex in orchestrator** — Pass one `ChunkIndex` into parallel `_search_one_variant` calls (process cache usually hits after first load).
- **Batch vector matmul** — Single `(variants, d) @ (n, d).T` instead of per-variant cosine loops in [`_vector_rank_parent`](ingestion/lib/search_hybrid.py).
- **Default prod retrieval slug on install** — Seed `runtime.json` `retrieval_model` on Mac mini install (e.g. `deepseek/deepseek-v4-flash` or Groq via playbook); today manual via `/setmodel retrieval …` and confirm via `/settings`.

### Janitor UX

- **Streaming clean preview** — Stream partial LLM output during clean on long pastes (expand subprocess already uses `--no-stream` in [`janitor_workflow.py`](services/telegram/bot/janitor_workflow.py)).
- **Edit catalog title in frontmatter** — Optional LLM pass for episode title (today from catalog only).
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail; [`expand_datapoints_llm.py`](ingestion/notes/expand_datapoints_llm.py) skips non-complete).
- **Janitor separate process** — Second bot for multi-user (deferred; today mode-switched via `/janitor` / `/librarian`).
- **BotFather persistent menu button** — Optional reply-keyboard shortcut; slash commands registered in [`app_factory.py`](services/telegram/bot/app_factory.py) (`setMyCommands`).

## Testing

From [`docs/testing.md`](docs/testing.md).

- **Ingestion CLI test coverage** — No dedicated pytest for `cli_args`, `expanded_timestamp_lint`, `x_posts_csv`, and most network CLIs (`fetch_transcripts`, `x_posts_sync`); rely on `verify.py` + manual checks.
- **Rebuilt-index v0 criterion in CI** — `test_v0_criterion_expanded_in_index` skipped unless `RUN_REBUILT_INDEX_SCENARIOS=1`; opt-in full-index scenarios in [`test_vault_retrieval_scenarios.py`](tests/test_vault_retrieval_scenarios.py).

## Retrieval / index

- **Repo-wide vector DB** — Do not add until grep + chunk index + agent tools fail real queries. Gate: [`docs/repo-agent-guide.md`](docs/repo-agent-guide.md), [`docs/retrieval.md`](docs/retrieval.md#graduate-to-repo-wide-embeddings-when). Telegram parent-tier embed index stays in scope for the bot.

**Explicit non-goals** (not backlog — use `load_episode` / `/sync` instead): multi-host / Cloud Run, section-filter commands (`/transcript`, `/post`, …), `/resume` auto-sync. [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md#non-goals).

## Content / catalog (manual)

Not code — tracked in docs until done.

- **X native article bodies** — ep-0082, ep-0088 need full article paste + `assign_post_manual.py`. [`catalog/import-review.md`](catalog/import-review.md), [`import/README.md`](import/README.md).
- **Notes placeholder** — ep-0021 still has `- XYZ` scaffold bullets. [`catalog/import-review.md`](catalog/import-review.md#open).
- **Post attribution queue** — Ambiguous rows in `catalog/post-mapping-review.jsonl`; resolve via attribute re-run or manual assign. [`ingestion/x/README.md`](ingestion/x/README.md).

## Ingestion

- **`expand_datapoints_llm.py --jobs N`** — Parallel expand workers (today: manual N× `--id` subprocesses). [`docs/expanded-backfill.md`](docs/expanded-backfill.md#parallel-expand-workers).
