# Harness scenarios

YAML flows for the [mock Telegram harness](../../docs/telegram-mock-harness.md). Not the same as vault retrieval JSONL (`ingestion/fixtures/vault_retrieval_scenarios.jsonl`).

On the Mac mini bot host, production models live in `~/.config/founders-telegram/runtime.json` (`/setmodel`). Live harness still accepts `TELEGRAM_CHAT_MODEL` in env or `librarian_model` in that file.

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

Live librarian runs write **schema v2** JSON to `dev/logs/runs/*-report.json` plus a paired `*-report.md` with formatted answers for preview. JSON includes `observability` (agent path, latency breakdown, cap thrash), legacy `timing`, and `stop_reason`. Suite runs also append `dev/logs/runs/librarian-suite-history.json`. See [telegram-mock-harness.md](../../docs/telegram-mock-harness.md#report-json-schema--reportjson).

## Key files

| File | Checks |
|------|--------|
| `librarian/episode_resolve.yaml` | NL “episode 191/22” → `load_episode`, `ep-0191` / `ep-0022` |
| `librarian/tool_coverage.yaml` | Core vault tools called (`search_vault`, `search_transcript`, `load_episode`, `list_episode_ids`) |
| `librarian/thematic_search.yaml` | Thematic Q → `search_vault`, citation e.g. `[ep-0016]` |
| `librarian/multi_founder_comparison.yaml` | Cross-founder → `search_vault_many` (live) |
| `librarian/multi_hop.yaml` | Multi-hop thematic → `search_vault_many` (live) |
| `librarian/thematic_cross_episode.yaml` | Cross-episode themes → `tool_called_any`: `search_vault` or `search_vault_many` (live) |
| `librarian/thin_evidence_probe.yaml` | Thin-evidence honesty probe (live) |
| `librarian/verbatim_transcript.yaml` | Verbatim → `search_transcript` (live) |
| `librarian/single_founder_depth.yaml` | Single-founder depth (live) |
| `janitor/episode_parse.yaml` | Paste line `191` resolves without NL regex in Librarian |
