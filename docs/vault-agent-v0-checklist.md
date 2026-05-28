# Vault agent v0 — verification checklist

Maps [telegram_rag_bot_v0.plan.md](../.cursor/plans/telegram_rag_bot_v0.plan.md) success criteria to automated tests and Mac mini handoffs.

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

Related retrieval/index guards: `tests/test_vault_retrieval_scenarios.py`, `tests/test_vault_agent.py` (`load_episode` / mock un-listened turn).

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

| Step | Command |
|------|---------|
| Nightly index | `chmod +x services/telegram/deploy/install-cron.sh && services/telegram/deploy/install-cron.sh` |
| Review cron line only | `services/telegram/deploy/install-cron.sh --print` |
| Manual sync | `services/telegram/deploy/sync-and-index.sh` |
| Bot reload after pull | `launchctl kickstart -k gui/$(id -u)/com.founders.telegram.bot` |

## Manual smoke (Telegram)

1. Thematic question (e.g. Rockefeller discipline) — synthesized answer with `[ep-NNNN]`, not transcript walls.
2. Same question without `/web` — no external facts mixed in.
3. Guest on an un-listened episode (e.g. Naval / ep-0191) — bot says you have **not studied** it yet; no transcript dump.
4. `/newchat` — file appears under `catalog/telegram-sessions/` on the bot host.
5. Second Telegram user (if configured) — blocked.
