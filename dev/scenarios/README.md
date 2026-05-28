# Harness scenarios

YAML flows for the [mock Telegram harness](../../docs/telegram-mock-harness.md). Not the same as vault retrieval JSONL (`ingestion/fixtures/vault_retrieval_scenarios.jsonl`).

## Suites

| Folder | `llm` | Purpose |
|--------|-------|---------|
| `librarian/` | `live` | Librarian tool loop, NL Q&A, episode resolution |
| `janitor/` | `echo` | Janitor FSM, paste parse (`191` → `ep-0191`); no OpenRouter in CI |

## Run

```bash
# CI parity (echo, all YAML)
pytest tests/test_harness_scenarios.py -q

# Preflight (keys + chunks + embeddings on this clone)
python dev/mock_telegram_cli.py --preflight

# Live Librarian only (~7 min; loads ~/.config/founders-telegram/env + repo .env)
python dev/mock_telegram_cli.py --suite librarian --live-only -v

# Single regression (episode bare-number fix)
python dev/mock_telegram_cli.py --scenario dev/scenarios/librarian/episode_resolve.yaml -v
```

`--suite` and `--scenario` **run scenarios** (no need for `--run-scenarios`). Bare `python dev/mock_telegram_cli.py` starts the REPL.

## Key files

| File | Checks |
|------|--------|
| `librarian/episode_resolve.yaml` | NL “episode 191/22” → `load_episode`, `ep-0191` / `ep-0022` |
| `librarian/tool_coverage.yaml` | All four vault tools called |
| `librarian/thematic_search.yaml` | Thematic Q → `search_vault_parent`, status line, `[ep-0016]` citation |
| `janitor/episode_parse.yaml` | Paste line `191` resolves without NL regex in Librarian |
