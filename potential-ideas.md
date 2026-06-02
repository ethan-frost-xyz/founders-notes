# Potential ideas

Deferred work only. Shipped behavior lives in the codebase and [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md) (runbooks: [`services/telegram/README.md`](services/telegram/README.md)). Historical plans: [`.cursor/plans/archive/legacy/`](.cursor/plans/archive/legacy/) (deep archive).

Pick one cluster → new `.cursor/plans/*.plan.md` → archive the plan when done → remove the cluster from this file (do not add a changelog section here).

## Telegram

### Ops / sync (recommended next)

- **Handler integration tests** — Mock [`ops_telegram.run_ops_job`](services/telegram/bot/ops_telegram.py) (lock busy, success/fail) and settings-panel ops callbacks; extend [`test_ops_runner.py`](tests/test_ops_runner.py) patterns. [`test_github_webhook.py`](tests/test_github_webhook.py) already covers webhook smoke. No live git/embeddings in CI. Manual `/sync` stays full pull + reindex.

**Defer:** Pull-only / path-filtered reindex on webhook when *all* changed paths match a strict allowlist (`docs/`, `tests/`, `services/telegram/`, `.cursor/`, root markdown); anything under `content/`, `catalog/`, or `ingestion/search/` → full reindex. False negative → stale search until `/sync`. Nightly cron stays full sync. Bundle in one plan only if code-only `main` pushes hurt.

### Harness / CI

- **Live librarian deploy smoke** — Before Mac mini deploy: `python dev/mock_telegram_cli.py --suite librarian --live-only` (or `RUN_LIVE_HARNESS=1 pytest … -k live`) when keys + index preflight pass. See [`docs/telegram-mock-harness.md`](docs/telegram-mock-harness.md).

### Agent / models

- **OpenRouter reasoning params** — Optional `reasoning.effort` in [`agent.py`](services/telegram/bot/agent.py) for Librarian synthesis only (thinking-capable models). `librarian_reasoning_effort` independent of `librarian_model`. Decide first: opt-in docs, retry without reasoning on 4xx, env-only, or model allowlist. [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

### Librarian latency

Operational tuning (no code): fast `retrieval_model` on the Mac mini — [`docs/janitor.md`](docs/janitor.md#model-tuning-playbook), [`docs/retrieval.md`](docs/retrieval.md).

- **Split expand vs rerank models** — Separate runtime keys for expand vs rerank.
- **Overlap embed with expand** — Start batched `embed_queries` when variants exist.
- **Cheaper rerank path** — Smaller pool, skip LLM rerank on high RRF confidence, or RRF-only on `follow_up`.
- **Local retrieval hygiene** — Cache `load_chunks()` across variant searches.
- **Default prod retrieval slug** — Document or seed Groq retrieval on mini install.

### Janitor UX

- **Streaming clean preview** — Stream partial LLM output during clean on long pastes.
- **Edit catalog title in frontmatter** — Optional LLM pass for episode title (today from catalog only).
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).
- **Janitor separate process** — Second bot for multi-user (deferred; today mode-switched).
- **BotFather persistent menu button** — Optional reply-keyboard shortcut; `/janitor` stays in `setMyCommands`.

## Ingestion

- **`expand_datapoints_llm.py --jobs N`** — Parallel expand workers. [`docs/expanded-backfill.md`](docs/expanded-backfill.md).