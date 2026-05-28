# Testing

CI runs from the **repo root** (see [`.github/workflows/verify.yml`](../.github/workflows/verify.yml)):

```bash
pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
pytest tests -q
cd ingestion && python pipeline/verify.py
```

[`tests/conftest.py`](../tests/conftest.py) calls `setup_ingestion_paths(REPO, include_subpackages=True)` from [`ingestion/_bootstrap.py`](../ingestion/_bootstrap.py) (adds `ingestion/`, `lib/`, `search/`, `notes/`, `x/`, `pipeline/`) and puts `services/telegram/bot` (+ `tools/`) on `sys.path` for Telegram tests.

## Test modules

| File | Covers |
|------|--------|
| `test_episode_ids.py` | `episode_ids` |
| `test_paths.py` | `paths` |
| `test_markdown_io.py` | `markdown_io` |
| `test_layout.py` | `layout` |
| `test_catalog.py` | `catalog.resolve_catalog_row` |
| `test_x_posts_match.py` | `x_posts_match` |
| `test_x_posts_threads.py` | `x_posts_threads` |
| `test_attribute_posts_llm.py` | `x/attribute_posts_llm.py` |
| `test_expand_llm.py` | `expand_llm` / `openrouter_client` / `expand_*` + `expand_datapoints_llm` apply/logging |
| `test_expand_tune.py` | `notes/expand_tune.py` |
| `test_openrouter_pricing.py` | `openrouter_pricing` |
| `test_expand_baseline_fixtures.py` | Committed `fixtures/expand-runs/baseline/` + `expand_tune verify` |
| `test_maintain.py` | `maintain.py` |
| `test_search_retrieval.py` | `search_retrieval` |
| `test_vault_agent.py` | Telegram `agent` + vault tools |
| `test_vault_v0_checklist.py` | v0 success criteria (mock agent + tools); see [vault-agent-v0-checklist.md](vault-agent-v0-checklist.md) |
| `test_vault_retrieval_scenarios.py` | Scenario JSONL against `chunks.jsonl` |
| `test_janitor_notes.py` | Janitor episode parse, finalize_notes_body, merge |
| `test_janitor_workflow.py` | Janitor LLM clean (mocked), catalog, prompt, `run_reindex` |
| `test_reindex_vault.py` | `reindex_vault` subprocess order, env, embeddings flag |
| `test_telegram_bot.py` | Telegram transport, sessions, deploy smoke |

## Focused runs

Telegram vault (no live API):

```bash
pytest tests/test_search_retrieval.py tests/test_vault_agent.py tests/test_vault_v0_checklist.py tests/test_telegram_bot.py -q
```

Rebuilt index (after `build_chunks.py`):

```bash
RUN_REBUILT_INDEX_SCENARIOS=1 pytest tests/test_vault_retrieval_scenarios.py tests/test_vault_v0_checklist.py -q
```

## “Legacy” in test names

Some tests mention legacy behavior (e.g. unpadded `ep-200`, old “Key takeaway” headings). Those **run in CI** — they guard supported backward compatibility, not deprecated code.

## Mock Telegram harness

Headless and REPL testing for the vault bot without the real Bot API. Uses the production handler stack with a mocked transport; Janitor writes go to a temp sandbox, not `content/notes/`.

```bash
pip install pyyaml   # or ingestion/requirements-dev.txt
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
python dev/mock_telegram_cli.py --suite librarian --debug
python dev/mock_telegram_cli.py --scenario dev/scenarios/librarian/basic_qa.yaml
```

Live OpenRouter mode (no `--stub-llm`): set `OPENROUTER_API_KEY` and `TELEGRAM_CHAT_MODEL`. `TELEGRAM_BOT_TOKEN` is not required.

Harness logs: `dev/logs/sessions/`, `dev/logs/runs/`, optional `dev/logs/sandbox/` with `--keep-sandbox`.

Parametrized echo scenarios (optional; not in default CI until stable):

```bash
pytest tests/test_harness_scenarios.py -q
SKIP_HARNESS_SCENARIOS=1 pytest tests -q   # skip harness module
```

## Gaps (no dedicated tests yet)

`cli_args`, `expanded_timestamp_lint`, `x_posts_csv`, and most network CLIs (`fetch_transcripts`, `sync_x_cache`) rely on `verify.py` and manual checks.
