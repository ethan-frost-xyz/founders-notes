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

**Suite size:** 47 `test_*.py` modules, ~341 tests collected (13 skipped in default CI: live harness scenarios + opt-in index checks).

Shared setup: [`conftest.py`](../tests/conftest.py) (paths, `agent_config`, vault chunk fixture). Helpers: [`search_test_helpers.py`](../tests/search_test_helpers.py) (retrieval scenarios), [`telegram_test_helpers.py`](../tests/telegram_test_helpers.py) (mock updates/contexts).

### Ingestion / vault layout

| File | Covers |
|------|--------|
| `test_episode_ids.py` | `episode_ids` |
| `test_paths.py` | `paths` |
| `test_markdown_io.py` | `markdown_io` |
| `test_layout.py` | `layout` |
| `test_catalog.py` | `catalog.resolve_catalog_row` |
| `test_maintain.py` | `maintain.py` |

### Chunk index and search

| File | Covers |
|------|--------|
| `test_build_chunks.py` | `build_chunks` — listened filter, line numbers, expanded datapoint splits |
| `test_build_summaries.py` | `build_summaries` — incremental hash skip / LLM call |
| `test_search_retrieval.py` | `search_retrieval`, `build_embeddings` (fixture slice, no API) |
| `test_retrieval_orchestrator.py` | `RetrievalOrchestrator.retrieve_core` (mocked expand/rerank) |
| `test_rerank_llm.py` | LLM reranker (`services/telegram/lib/retrieval/rerank_llm.py`) |
| `test_vault_retrieval_scenarios.py` | Retrieval scenario JSONL (fixture index in CI) |
| `test_reindex_vault.py` | `reindex_vault` subprocess order, env, embeddings flag |
| `test_vault_ops.py` | `vault_ops` git pull / reindex wrappers |

### Expand pipeline

| File | Covers |
|------|--------|
| `test_expand_llm.py` | `expand_prompt` / `openrouter_client` / `expand_*` + `expand_datapoints_llm` apply/logging |
| `test_expand_tune.py` | `notes/expand_tune.py` |
| `test_openrouter_pricing.py` | `openrouter_pricing` |

### X posts pipeline

| File | Covers |
|------|--------|
| `test_x_posts_match.py` | `x_posts_match` |
| `test_x_posts_threads.py` | `x_posts_threads` |
| `test_x_posts_chrono.py` | `x_posts_chrono` sequential gap-fill |
| `test_x_post_attribution.py` | `x_post_attribution` cascade (LLM mocked) |
| `test_x_posts_pending.py` | `x_posts_pending` queue dedupe |
| `test_x_sync_fetch.py` | `x_sync_fetch` windowed/backfill fetch (mocked API) |

### Telegram Librarian (bot core)

| File | Covers |
|------|--------|
| `test_vault_agent.py` | Telegram `agent` + vault tools (`load_episode` candidates, orchestrator trace) |
| `test_evidence_format.py` | Librarian evidence / load-episode formatting |
| `test_librarian_prompt.py` | Librarian system prompt assembly |
| `test_reply_sanitize.py` | Reply leak sanitization (DSML / markup) |
| `test_turn_timing.py` | Turn timing telemetry (`TurnTimer`, `search_vault` error recording) |
| `test_runtime_settings.py` | `runtime.json` overrides (`stream_replies`, librarian/retrieval/janitor/expand/embed models, Janitor temp) |
| `test_telegram_bot.py` | Auth, sessions, message split/HTML (no live Bot API) |
| `test_vault_v0_checklist.py` | v0-only criteria; see [Vault agent v0 checklist](#vault-agent-v0-checklist) |

### Telegram handlers (mocked, fast)

| File | Covers |
|------|--------|
| `test_telegram_handlers.py` | Librarian `on_text` — agent turn, streaming, tool status |
| `test_janitor_handlers.py` | Janitor FSM callbacks (mocked LLM/workflow) |
| `test_settings_handlers.py` | Settings tap UI presets and callback dispatch |
| `test_ui_keyboards.py` | Shared inline keyboard helpers |
| `test_app_factory.py` | `build_application()` handler registration |

### Mock harness

| File | Covers |
|------|--------|
| `test_harness_scenarios.py` | YAML scenarios (echo in CI; opt-in live via `RUN_LIVE_HARNESS=1`) |
| `test_harness_trace_report.py` | Harness trace extractors, expectation checker, report writer |
| `test_harness_env.py` | Live harness OpenRouter preflight |
| `test_mock_telegram_cli.py` | Harness CLI flags (`--suite` implies run, live scenario discovery) |

### Janitor workflow

| File | Covers |
|------|--------|
| `test_janitor_notes.py` | Episode parse, `finalize_notes_body`, merge |
| `test_janitor_workflow.py` | LLM clean (mocked), catalog, prompt, `run_reindex` |

### Ops / deploy

| File | Covers |
|------|--------|
| `test_telegram_deploy.py` | Deploy artifacts + `install-*.sh --print` |
| `test_export_runtime_env.py` | `runtime.json` → shell export (`sync-and-index.sh`) |
| `test_ops_runner.py` | Ops runner lock and git pull helpers |
| `test_ops_telegram.py` | Async ops job wrappers (Telegram commands / settings panel) |
| `test_github_webhook.py` | GitHub webhook HMAC, ping, push filtering |

## Focused runs

Default CI-equivalent full suite:

```bash
pytest tests -q
```

Telegram vault (no live API):

```bash
pytest tests/test_search_retrieval.py tests/test_retrieval_orchestrator.py \
  tests/test_vault_agent.py tests/test_vault_v0_checklist.py tests/test_telegram_bot.py \
  tests/test_vault_retrieval_scenarios.py -q
```

Telegram handlers (mocked agent/workflow, no harness):

```bash
pytest tests/test_telegram_handlers.py tests/test_janitor_handlers.py \
  tests/test_settings_handlers.py tests/test_ui_keyboards.py tests/test_app_factory.py -q
```

Retrieval + timing stack:

```bash
pytest tests/test_search_retrieval.py tests/test_retrieval_orchestrator.py \
  tests/test_rerank_llm.py tests/test_evidence_format.py tests/test_turn_timing.py -q
```

X posts pipeline:

```bash
pytest tests/test_x_posts_match.py tests/test_x_posts_threads.py tests/test_x_posts_chrono.py \
  tests/test_x_post_attribution.py tests/test_x_posts_pending.py tests/test_x_sync_fetch.py -q
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

Maps shipped Telegram agent criteria to automated tests. Criteria #1, #3, #4, and unlistened search index checks live in canonical modules (see table); `test_vault_v0_checklist.py` holds v0-only agent/index checks. Overview: [telegram-vault-agent.md](telegram-vault-agent.md). Ops: [operations.md](operations.md).

```bash
pytest tests/test_vault_v0_checklist.py tests/test_vault_agent.py \
  tests/test_telegram_bot.py tests/test_vault_retrieval_scenarios.py -q
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

Full guide: **[telegram-mock-harness.md](telegram-mock-harness.md)**.

```bash
python dev/mock_telegram_cli.py --stub-llm --run-scenarios
```

## Gaps (no dedicated tests yet)

`cli_args`, `expanded_timestamp_lint`, `x_posts_csv`, and network CLIs that only wrap lib code (`fetch_transcripts`, `x/x_posts_sync.py` entrypoint) rely on `verify.py`, lib unit tests where they exist, and manual checks. `build_summaries` and `x_sync_fetch` have unit tests; their CLI wrappers do not.
