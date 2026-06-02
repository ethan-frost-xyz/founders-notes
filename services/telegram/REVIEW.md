# Review guide — Telegram vault bot (v0)

**Historical SP1–SP4 PR review.** Shipped on `main`. For current operator and test docs, use [README.md](README.md), [docs/telegram-vault-agent.md](../../docs/telegram-vault-agent.md), [docs/testing.md](../../docs/testing.md), and [docs/telegram-mock-harness.md](../../docs/telegram-mock-harness.md) — do not maintain a second runbook here.

Use this when reviewing historical SP1–SP4 commits. **Do not review commit-by-commit noise** — walk SP1→SP4 in order.

## TL;DR

Private Telegram bot: OpenRouter **tool-calling** agent over the Founders vault (hybrid parent-tier search + transcript tools). Not single-shot RAG. Full repo test suite: `pytest tests -q` from repo root (no API keys for default CI; harness uses echo LLM).

## Commit map (review in order)

| Commit | Focus | Start here |
|--------|--------|------------|
| SP1 | Retrieval + embed index + `vault.py` tools | `ingestion/lib/search_retrieval.py`, `ingestion/search/build_embeddings.py`, `services/telegram/bot/tools/vault.py` |
| SP2 | Agent loop + prompt | `services/telegram/bot/agent.py`, `services/telegram/prompts/vault_agent.md` |
| SP3 | Telegram transport + sessions | `services/telegram/bot/handlers.py`, `sessions.py`, `auth.py` |
| SP4 | Mac mini ops | `services/telegram/deploy/*`, README install section |

Plans (context only, archived): `telegram_vault_sp*.plan.md` under [`.cursor/plans/archive/`](../../.cursor/plans/archive/), [telegram_mock_harness_2296d9fc.plan.md](../../.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md).

## Core vs mechanical

**Core (behavior + contracts)**

- `ingestion/lib/search_retrieval.py` — parent/transcript filters, keyword, optional vectors, RRF hybrid, tier boost (`expanded` > `notes` > `post`)
- `services/telegram/bot/tools/vault.py` — JSON evidence for agent tools
- `services/telegram/bot/agent.py` — OpenRouter loop, `allow_web` gate, tool dispatch
- `services/telegram/bot/handlers.py` — allowlist, `/web` only when requested

**Mechanical / ops**

- `ingestion/search/build_embeddings.py`, `.gitignore` entries for `catalog/embeddings.*`
- `services/telegram/deploy/*` — launchd template, shell wrappers
- `ingestion/fixtures/chunks_parent_slice.jsonl` — test fixture only

**Tests** (mock OpenRouter; fixture chunks; see [docs/testing.md](../../docs/testing.md) **Focused runs**)

- `tests/test_search_retrieval.py`
- `tests/test_vault_agent.py`
- `tests/test_vault_v0_checklist.py`
- `tests/test_vault_retrieval_scenarios.py` — JSONL index quality (not harness YAML)
- `tests/test_janitor_notes.py`, `tests/test_janitor_workflow.py`
- `tests/test_telegram_bot.py` — transport, sessions, deploy smoke
- `tests/test_telegram_deploy.py` — deploy script smoke
- `tests/test_harness_scenarios.py` — `dev/scenarios/**/*.yaml` (echo, default CI)
- `dev/mock_telegram_cli.py` — local REPL and scenario runner ([telegram-mock-harness.md](../../docs/telegram-mock-harness.md))

## Risk areas

1. **Path / import wiring** — [`ingestion/_bootstrap.py`](../../ingestion/_bootstrap.py) (`resolve_vault_root`, `setup_ingestion_paths`); bot entry in `bot/__main__.py`, Librarian via [`config.setup_bot_paths`](bot/config.py). Confirm `VAULT_ROOT` points at repo root on Mac mini.
2. **Embeddings optional** — hybrid falls back to keyword-only if `catalog/embeddings.npy` missing; vector path needs `OPENROUTER_API_KEY` + `build_embeddings.py`.
3. **`/web` tool** — `web_search` in [`bot/tools/web.py`](bot/tools/web.py) returns `provider not implemented` until `WEB_SEARCH_API_KEY` is set and a provider is wired; normal messages use `allow_web=false` (verify in `handlers.py` + `agent.py`).
4. **Index staleness** — v0: manual/cron `sync-and-index.sh`; no lock during active turns (documented in README).
5. **Scope vs AGENTS.md** — parent-tier embed index only inside `search_vault_parent`; not a repo-wide vector DB.

Long agent replies are split in `messaging.split_telegram_text` (4096-char Bot API limit) via `reply_text_chunked` in handlers.

## Out of scope for this PR

- Expanded draft files, `catalog/gaps.md`, unrelated plan archive edits on your working tree
- Open follow-ups → [`potential-ideas.md`](../../potential-ideas.md)
- Live OpenRouter / Telegram smoke (requires secrets)

## Test plan

See [docs/testing.md](../../docs/testing.md). Quick slice:

```bash
cd /path/to/founders-notes
ingestion/.venv/bin/pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
ingestion/.venv/bin/python -m pytest tests -q
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

Optional: `python pipeline/verify.py` from `ingestion/` (repo verify; unchanged contract).

## Post-merge (operator)

1. Copy `deploy/env.example` → `~/.config/founders-telegram/env` (secrets only; models go in `runtime.json` after first `/restart` seeds from legacy env)
2. Run `deploy/sync-and-index.sh` once (or Telegram `/sync` when the bot is up)
3. Install launchd plist per `services/telegram/README.md`
