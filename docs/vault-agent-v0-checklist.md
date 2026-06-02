# Vault agent v0 — verification checklist

Maps v0 success criteria (shipped Telegram vault agent) to automated tests and Mac mini handoffs. Overview: [`telegram-vault-agent.md`](telegram-vault-agent.md).

## Automated (CI)

Run from repo root:

```bash
pytest tests/test_vault_v0_checklist.py -q
```

| # | Criterion | Test |
|---|-----------|------|
| 1 | Thematic Q → `search_vault_parent` in trace | `test_v0_criterion_search_parent_in_trace` |
| 2 | Web only when allowed (`/web` path) | `test_v0_criterion_web_gated` |
| 3 | After promote + reindex → `expanded:*` in hybrid hits | `test_v0_criterion_expanded_in_index` (skip unless `RUN_REBUILT_INDEX_SCENARIOS=1`) |
| 4 | Allowlist blocks non-user | `test_v0_criterion_allowlist` |
| 5 | `/newchat` exports valid session jsonl | `test_v0_criterion_newchat_export` |
| — | Un-listened episode absent from search index | `test_v0_criterion_unlistened_no_hits` |

Related retrieval/index guards: `tests/test_vault_retrieval_scenarios.py`, `tests/test_vault_agent.py` (`load_episode` / mock un-listened turn). Un-listened examples use **ep-0400** (scaffold notes only); ep-0191 is studied and used for resolution/Janitor harness examples elsewhere.

Rebuilt-index validation (after `build_chunks.py` changes):

```bash
RUN_REBUILT_INDEX_SCENARIOS=1 pytest tests/test_vault_retrieval_scenarios.py tests/test_vault_v0_checklist.py -q
```

Deploy smoke (cron line shape, no live `crontab` write):

```bash
pytest tests/test_telegram_bot.py -k cron -q
```

## Local harness (commands + Janitor FSM)

Handler and command smoke without Telegram, Bot API token, or OpenRouter keys (echo LLM):

```bash
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
pytest tests/test_harness_scenarios.py -q
```

Guide: [telegram-mock-harness.md](telegram-mock-harness.md). **Retrieval JSONL** scenarios (`test_vault_retrieval_scenarios.py` + `RUN_REBUILT_INDEX_SCENARIOS=1`) measure chunk index quality only — not bot UX.

## Mac mini (operator)

Production host runbook: [mac-mini-operator-setup.md](mac-mini-operator-setup.md) (status, restart, webhook verification).

| Step | Command |
|------|---------|
| Auto sync after merge to `main` | GitHub webhook → `sync-and-index.sh` (verify ping **200** in repo Settings → Webhooks) |
| Nightly index | `install-cron.sh` (optional; production host has this) |
| Manual sync fallback | Telegram `/sync` when idle, or `sync-and-index.sh` |
| Restart bot + webhook | See [restart block](mac-mini-operator-setup.md#mac-mini--status--restart-paste-in-terminal) |
| Git pull for scripts | Remote must be SSH: `git@github.com:ethan-frost-xyz/founders-notes.git` |

## Manual smoke (Telegram)

NL episode resolution (mock harness live): `python dev/mock_telegram_cli.py --scenario dev/scenarios/librarian/episode_resolve.yaml -v` (env auto-loaded; see [telegram-mock-harness.md](telegram-mock-harness.md)).

1. Thematic question (e.g. Rockefeller discipline) — synthesized answer with `[ep-NNNN]`, not transcript walls.
2. Same question without `/web` — no external facts mixed in.
3. Guest on an un-listened episode (e.g. James Dyson / ep-0400) — bot says you have **not studied** it yet; no transcript dump.
4. `/newchat` — file appears under `catalog/telegram-sessions/` on the bot host.
5. Second Telegram user (if configured) — blocked.
