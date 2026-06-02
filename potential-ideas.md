# Potential ideas

Deferred work only. Shipped behavior lives in the codebase and [`docs/telegram-vault-agent.md`](docs/telegram-vault-agent.md) (runbooks: [`services/telegram/README.md`](services/telegram/README.md)). Historical plans: [`.cursor/plans/archive/legacy/`](.cursor/plans/archive/legacy/) (deep archive).

Pick one cluster → new `.cursor/plans/*.plan.md` → archive the plan when done → remove the cluster from this file (do not add a changelog section here).

## Ops / Tailscale (laptop ↔ Mac mini)

Cross-host admin so the laptop (and Cursor agent) can reach the always-on bot host without sitting at the mini. Telegram remains the primary day-to-day control; SSH is optional recovery and verification.

**Done (2026-06):**

- Tailscale on Mac mini (`ethans-mac-mini`, tailnet `ethan-frost-xyz@`)
- Tailscale on laptop (`ethans-macbook-air`), same tailnet — `tailscale ping ethans-mac-mini` succeeds

**Pending:**

- **Remote Login on mini** — System Settings → General → Sharing → Remote Login (today: SSH port 22 refused from laptop)
- **Optional Screen Sharing on mini** — same Sharing pane; enables `vnc://ethans-mac-mini` from laptop when needed
- **SSH from laptop** — `ssh <mini-mac-username>@ethans-mac-mini` (username likely `ethanfrost` per [operations.md](docs/operations.md) paths)
- **SSH key auth** — `ssh-keygen` on laptop if needed, then `ssh-copy-id <user>@ethans-mac-mini`
- **`~/.ssh/config` on laptop** — `Host ethans-mac-mini` → `HostName ethans-mac-mini`, `User <username>`
- **Prod model split (Telegram, no SSH required)** — `/setmodel retrieval deepseek/deepseek-v4-flash`; keep `librarian_model` on `deepseek/deepseek-v4-pro`; confirm with `/settings` + one thematic Librarian question
- **Verify mini `runtime.json`** — after SSH works: `cat ~/.config/founders-telegram/runtime.json` on mini matches `/settings`
- **Docs touch-up** — [operations.md](docs/operations.md) “Tailscale (laptop ↔ Mac mini)” (done 2026-06)

**Verify tailnet (laptop terminal):**

```bash
tailscale status          # both machines listed, same account
tailscale ping ethans-mac-mini
nc -zv ethans-mac-mini 22   # open after Remote Login; refused until then
```

**Not required for Tailscale laptop setup:** Tailscale Funnel on laptop (Funnel runs on mini for GitHub → `sync-and-index.sh` only).

## Telegram

### Ops / sync (recommended next)

- **Handler integration tests** — Mock [`ops_telegram.run_ops_job`](services/telegram/bot/ops_telegram.py) (lock busy, success/fail) and settings-panel ops callbacks; extend [`test_ops_runner.py`](tests/test_ops_runner.py) patterns. [`test_github_webhook.py`](tests/test_github_webhook.py) already covers webhook smoke. No live git/embeddings in CI. Manual `/sync` stays full pull + reindex.

**Defer:** Pull-only / path-filtered reindex on webhook when *all* changed paths match a strict allowlist (`docs/`, `tests/`, `services/telegram/`, `.cursor/`, root markdown); anything under `content/`, `catalog/`, or `ingestion/search/` → full reindex. False negative → stale search until `/sync`. Nightly cron stays full sync. Bundle in one plan only if code-only `main` pushes hurt.

### Harness / CI

- **Live librarian deploy smoke** — Before Mac mini deploy: `python dev/mock_telegram_cli.py --suite librarian --live-only` (or `RUN_LIVE_HARNESS=1 pytest … -k live`) when keys + index preflight pass. See [`docs/telegram-mock-harness.md`](docs/telegram-mock-harness.md).

### Agent / models

- **OpenRouter reasoning params** — Optional `reasoning.effort` in [`agent.py`](services/telegram/bot/agent.py) for Librarian synthesis only (thinking-capable models). `librarian_reasoning_effort` independent of `librarian_model`. Decide first: opt-in docs, retry without reasoning on 4xx, env-only, or model allowlist. [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

### Agentic retrieval (recommended next for Librarian depth)

- **`search_vault` synthesis tool** — Let Librarian re-invoke the orchestrator (or a slim search-only path) when evidence is thin or a near-miss; update [`AGENTS.md`](AGENTS.md) “Retrieval already ran” rule when shipped.
- **Multi-hop turns** — Cap at N search rounds per thematic question; trace in `tool_trace`.
- **Fast path unchanged** — Simple questions stay single orchestrator pass (current v3 latency).

See also **Librarian latency** below (parallel variant search shipped; `load_chunks()` cache and batch vector matmul still open).

### Librarian latency

Operational tuning (no code): fast `retrieval_model` on the Mac mini — [`docs/janitor.md`](docs/janitor.md#model-tuning-playbook), [`docs/retrieval.md`](docs/retrieval.md).

- **Split expand vs rerank models** — Separate runtime keys for expand vs rerank.
- **Overlap embed with expand** — Start batched `embed_queries` when variants exist.
- **Cheaper rerank path** — Smaller pool, skip LLM rerank on high RRF confidence, or RRF-only on `follow_up`.
- **Local retrieval hygiene** — Cache `load_chunks()` across variant searches (parallel search shipped in orchestrator).
- **Batch vector matmul** — Single `(variants, d) @ (n, d).T` instead of per-variant cosine loops.
- **Default prod retrieval slug** — Seed `deepseek/deepseek-v4-flash` for `retrieval_model` on mini install (or Groq via [janitor.md](docs/janitor.md#model-tuning-playbook)); see Ops / Tailscale pending item for Telegram `/setmodel`.

### Janitor UX

- **Streaming clean preview** — Stream partial LLM output during clean on long pastes.
- **Edit catalog title in frontmatter** — Optional LLM pass for episode title (today from catalog only).
- **Janitor on episodes without transcript** — `transcript_status != complete` (expand may fail).
- **Janitor separate process** — Second bot for multi-user (deferred; today mode-switched).
- **BotFather persistent menu button** — Optional reply-keyboard shortcut; `/janitor` stays in `setMyCommands`.

## Ingestion

- **`expand_datapoints_llm.py --jobs N`** — Parallel expand workers. [`docs/expanded-backfill.md`](docs/expanded-backfill.md).