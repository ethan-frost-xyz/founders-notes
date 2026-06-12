# Testing

CI runs from the **repo root** (see [`.github/workflows/verify.yml`](../.github/workflows/verify.yml)):

```bash
pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt
pytest tests -q --durations=10
cd ingestion && python pipeline/verify.py
```

**Typical CI budget (after index fixture + caching):** pytest ~1–3 minutes, `verify.py` &lt;1s, pip install ~10–15s (cached on repeat runs). Previously pytest alone was ~11 minutes when every vault search re-parsed the full `catalog/chunks.jsonl` (~4,600 lines).

[`tests/conftest.py`](../tests/conftest.py) calls `setup_ingestion_paths(REPO, include_subpackages=True)` from [`ingestion/_bootstrap.py`](../ingestion/_bootstrap.py) (adds `ingestion/`, `lib/`, `search/`, `notes/`, `x/`, `pipeline/`) and puts `services/telegram/bot` (+ `tools/`) on `sys.path` for Telegram tests.

## Index reads and vault tests

- **Production:** [`ingestion/lib/catalog.py`](../ingestion/lib/catalog.py) caches JSONL reads (`load_jsonl`, `load_catalog`, and thus `load_chunks` / manifest loads). [`clear_jsonl_cache()`](../ingestion/lib/catalog.py) runs after `save_catalog`, `build_chunks`, and `build_embeddings` writes in the same process.
- **Vault integration tests** (`test_vault_*.py`): autouse patch of `paths.CHUNKS_PATH` → [`tests/fixtures/vault_search_chunks.jsonl`](../tests/fixtures/vault_search_chunks.jsonl) (small slice aligned with [`tests/fixtures/vault_retrieval_scenarios.jsonl`](../tests/fixtures/vault_retrieval_scenarios.jsonl)). Shared [`agent_config`](../tests/conftest.py) fixture for the same index.
- **Search unit tests** still use [`ingestion/fixtures/chunks_parent_slice.jsonl`](../ingestion/fixtures/chunks_parent_slice.jsonl) via `test_search_retrieval.py`.

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
| `test_expand_llm.py` | `expand_prompt` / `openrouter_client` / `expand_*` + `expand_datapoints_llm` apply/logging |
| `test_expand_tune.py` | `notes/expand_tune.py` |
| `test_openrouter_pricing.py` | `openrouter_pricing` |
| `test_maintain.py` | `maintain.py` |
| `test_build_chunks.py` | `build_chunks` — listened filter, line numbers, expanded datapoint splits |
| `test_search_retrieval.py` | `search_retrieval` |
| `test_vault_agent.py` | Telegram `agent` + vault tools (`load_episode` candidates, orchestrator trace) |
| `test_runtime_settings.py` | `runtime.json` overrides (`stream_replies`, librarian/retrieval/janitor/expand/embed models, Janitor temp) |
| `test_vault_v0_checklist.py` | v0 success criteria (mock agent + tools); see [Vault agent v0 checklist](#vault-agent-v0-checklist) below |
| `test_vault_retrieval_scenarios.py` | Retrieval scenario JSONL (fixture index in CI) |
| `test_janitor_notes.py` | Janitor episode parse, finalize_notes_body, merge |
| `test_janitor_workflow.py` | Janitor LLM clean (mocked), catalog, prompt, `run_reindex` |
| `test_reindex_vault.py` | `reindex_vault` subprocess order, env, embeddings flag |
| `test_telegram_bot.py` | Telegram transport, sessions, deploy smoke |
| `test_telegram_deploy.py` | Deploy artifacts + `install-*.sh --print` |
| `test_harness_scenarios.py` | Mock Telegram YAML scenarios (echo in CI; opt-in live via `RUN_LIVE_HARNESS=1`) |
| `test_mock_telegram_cli.py` | Harness CLI flags (`--suite` implies run, live scenario discovery) |

## Focused runs

Default CI-equivalent full suite:

```bash
pytest tests -q
```

Telegram vault (no live API):

```bash
pytest tests/test_search_retrieval.py tests/test_vault_agent.py tests/test_vault_v0_checklist.py tests/test_telegram_bot.py -q
```

Mock Telegram harness (echo, no Bot API token):

```bash
pytest tests/test_harness_scenarios.py -q
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

Harness echo scenarios are **not** the CI time sink (they share the fast ~seconds bucket with unit tests). Opt out of harness in a full run:

```bash
SKIP_HARNESS_SCENARIOS=1 pytest tests -q
```

Live Librarian harness (OpenRouter; loads `~/.config/founders-telegram/env` + repo `.env`; models from `~/.config/founders-telegram/runtime.json` on the Mac mini, or legacy env vars on any host):

```bash
python dev/mock_telegram_cli.py --suite librarian --live-only -v
# or opt-in pytest:
RUN_LIVE_HARNESS=1 pytest tests/test_harness_scenarios.py -k live -q
```

15 librarian scenarios including agentic stress (OOD, constraints, verbatim routing, tool efficiency) — see [telegram-mock-harness.md](telegram-mock-harness.md#agentic-stress-scenarios).

Janitor unit tests:

```bash
pytest tests/test_janitor_notes.py tests/test_janitor_workflow.py -q
```

Full production chunk index (listen-filter size + optional rebuilt-index scenarios):

```bash
RUN_FULL_INDEX_SCENARIOS=1 pytest tests/test_vault_retrieval_scenarios.py tests/test_vault_v0_checklist.py -q
```

Rebuilt embeddings / expanded sections in index (opt-in):

```bash
RUN_REBUILT_INDEX_SCENARIOS=1 pytest tests/test_vault_retrieval_scenarios.py tests/test_vault_v0_checklist.py -q
```

## Two kinds of scenarios

| | Mock Telegram harness | Vault retrieval scenarios |
|--|------------------------|---------------------------|
| **Purpose** | Bot handlers, commands, Janitor FSM, replies | Chunk index / hybrid search quality |
| **Data** | `dev/scenarios/**/*.yaml` | `tests/fixtures/vault_retrieval_scenarios.jsonl` |
| **Index in CI** | Real vault paths (Janitor sandbox is tiny) | `tests/fixtures/vault_search_chunks.jsonl` |
| **Tests** | `test_harness_scenarios.py` | `test_vault_retrieval_scenarios.py` |
| **Guide** | [telegram-mock-harness.md](telegram-mock-harness.md) | This doc, [Vault agent v0 checklist](#vault-agent-v0-checklist) |

## Vault agent v0 checklist

Maps shipped Telegram agent criteria to automated tests. Overview: [telegram-vault-agent.md](telegram-vault-agent.md). Ops: [operations.md](operations.md).

```bash
pytest tests/test_vault_v0_checklist.py -q
```

| # | Criterion | Test |
|---|-----------|------|
| 1 | Thematic Q → `search_vault` in trace | `test_run_turn_search_vault_tool_trace` in `test_vault_agent.py` |
| 2 | After promote + reindex → `expanded:*` in hybrid hits | `test_v0_criterion_expanded_in_index` (skip unless `RUN_REBUILT_INDEX_SCENARIOS=1`) |
| 3 | Allowlist blocks non-user | `test_is_allowed_rejects_unknown_user` in `test_telegram_bot.py` |
| 4 | `/newchat` exports valid session jsonl | `test_newchat_exports_valid_jsonl` in `test_telegram_bot.py` |
| — | Un-listened episode absent from search index | `test_vault_retrieval_scenario[unlistened_vault_parent]` + `[unlistened_transcript]` |
| — | Un-listened `load_episode` payload | `test_v0_criterion_unlistened_load_episode` |
| — | Un-listened agent response UX | `test_v0_criterion_unlistened_agent_response` |

Related: `test_vault_retrieval_scenarios.py`, `test_vault_agent.py`, `test_runtime_settings.py` (`stream_replies`).

Rebuilt-index validation:

```bash
RUN_REBUILT_INDEX_SCENARIOS=1 pytest tests/test_vault_retrieval_scenarios.py tests/test_vault_v0_checklist.py -q
```

Manual Telegram smoke: thematic Q with `[ep-NNNN]`; un-listened guest (ep-0400); `/newchat` export; `/settings` stream toggle.

## “Legacy” in test names

Some tests mention legacy behavior (e.g. old “Key takeaway” headings). Those **run in CI** where still applicable.

Harness **echo** mode intentionally skips `expect_live` assertions in YAML scenarios; that is not legacy product behavior.

## Mock Telegram harness

Headless and REPL testing without the real Bot API. Uses the production handler stack with a mocked transport; Janitor writes go to a temp sandbox under `dev/logs/sandbox/`, not `content/notes/`.

Full guide: **[telegram-mock-harness.md](telegram-mock-harness.md)**. Live librarian reports use **schema v2.0** with per-turn `observability` (agent pathing, latency spans, cap thrash) when timing is enabled.

```bash
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

## Gaps (no dedicated tests yet)

`cli_args`, `expanded_timestamp_lint`, `x_posts_csv`, and most network CLIs (`fetch_transcripts`, `x_posts_sync`) rely on `verify.py` and manual checks.
