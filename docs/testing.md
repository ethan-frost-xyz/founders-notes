# Testing

CI runs from the **repo root** (see [`.github/workflows/verify.yml`](../.github/workflows/verify.yml)):

```bash
pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
pytest tests -q
cd ingestion && python pipeline/verify.py
```

[`tests/conftest.py`](../tests/conftest.py) adds `ingestion/`, `ingestion/lib/`, `ingestion/notes/`, and `ingestion/x/` to `sys.path` for imports.

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
| `test_expand_llm.py` | `expand_llm` + `expand_datapoints_llm` apply/logging |
| `test_expand_tune.py` | `notes/expand_tune.py` |
| `test_openrouter_pricing.py` | `openrouter_pricing` |
| `test_expand_baseline_fixtures.py` | Committed `fixtures/expand-runs/baseline/` + `expand_tune verify` |
| `test_maintain.py` | `maintain.py` |
| `test_search_retrieval.py` | `search_retrieval` |
| `test_vault_agent.py` | Telegram `agent` + vault tools |
| `test_vault_v0_checklist.py` | v0 success criteria (mock agent + tools); see [vault-agent-v0-checklist.md](vault-agent-v0-checklist.md) |
| `test_vault_retrieval_scenarios.py` | Scenario JSONL against `chunks.jsonl` |
| `test_janitor_notes.py` | Janitor episode parse, finalize_notes_body, merge |
| `test_janitor_workflow.py` | Janitor LLM clean (mocked), catalog, prompt |
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

## Gaps (no dedicated tests yet)

`cli_args`, `expanded_timestamp_lint`, `x_posts_csv`, and most network CLIs (`fetch_transcripts`, `sync_x_cache`) rely on `verify.py` and manual checks.
