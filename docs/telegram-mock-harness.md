# Telegram mock harness

Headless and interactive testing for the **Librarian** and **Janitor** Telegram bot without the real Bot API. The harness runs the production handler stack (`build_application()`) with a mocked outbound transport; handler routing, sessions, Janitor FSM, and tool loops behave like production.

**When to use:** Before shipping handler or Janitor changes; adding YAML regressions; tuning agent prompts locally.

**Related:** [testing.md](testing.md) (CI and test-module index) · [services/telegram/README.md](../services/telegram/README.md) (Mac mini runbook) · [janitor.md](janitor.md) (operator workflow)

## Quick start

From repo root (after `pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt`):

```bash
# All scenarios, echo LLM (no API keys)
python dev/mock_telegram_cli.py --stub-llm --run-scenarios

# One suite or file
python dev/mock_telegram_cli.py --stub-llm --suite librarian
python dev/mock_telegram_cli.py --stub-llm --scenario dev/scenarios/janitor/episode_parse.yaml

# Interactive REPL with tool traces (echo — use --stub-llm)
python dev/mock_telegram_cli.py --stub-llm --debug
```

`TELEGRAM_BOT_TOKEN` is never required.

## Echo vs live

| Mode | How | API key | Assertions checked |
|------|-----|---------|-------------------|
| **Echo** | `--stub-llm` on CLI, or `llm: echo` in scenario YAML | Not required | `contains`, `not_contains`, `response_min_length`; Janitor `phase`, `sandbox_file_written` |
| **Live** | Omit `--stub-llm` and use `llm: live` in YAML | `OPENROUTER_API_KEY`, `TELEGRAM_CHAT_MODEL` | Echo assertions plus `expect_live`: `tool_called`, `response_contains` |

In **echo** mode, `expect_live` blocks in YAML are skipped (CI uses echo only). Librarian scenarios marked `llm: live` still run in echo when you pass `--stub-llm` or when `tests/test_harness_scenarios.py` sets `stub_llm=True`.

**Live smoke (optional):**

```bash
export OPENROUTER_API_KEY=... TELEGRAM_CHAT_MODEL=...
python dev/mock_telegram_cli.py --suite librarian
```

## REPL default

Running `python dev/mock_telegram_cli.py` **without** `--run-scenarios` starts an interactive REPL. The default LLM mode is **live** (needs OpenRouter env). For keyless local debugging, always pass **`--stub-llm`**.

## Janitor sandbox

Janitor scenarios set `janitor_episode` (e.g. `ep-0191`). Writes go to a temp tree under `dev/logs/sandbox/`, never to `content/notes/` in the real vault.

- In-process paths are patched via [`dev/harness/janitor_sandbox.py`](../dev/harness/janitor_sandbox.py).
- Echo mode stubs expand/reindex subprocesses; full workflow is still exercised for handlers and buttons.

Use `--keep-sandbox` on the CLI to preserve sandbox dirs after a run.

## Scenario YAML

Files live under [`dev/scenarios/`](../dev/scenarios/) (`librarian/`, `janitor/`).

| Field | Purpose |
|-------|---------|
| `name` | Display name in reports |
| `llm` | `echo` or `live` (overridden by CLI `--stub-llm`) |
| `janitor_episode` | Episode id for Janitor sandbox |
| `turns` | List of steps |

Each turn:

| Key | Purpose |
|-----|---------|
| `send` | User message text |
| `button` | Inline callback data (optional; can follow `send` in same turn) |
| `expect` | Assertions (see below) |

**Expect keys:** `contains`, `not_contains`, `response_min_length`, `expect_live` (`tool_called`, `response_contains`), `phase` (Janitor), `sandbox_file_written` (substring match on sandbox paths).

Example (Janitor parse smoke):

```yaml
name: Janitor episode parse formats
janitor_episode: ep-0191
llm: echo
turns:
  - send: "/janitor"
    expect:
      contains: "Janitor"
  - send: "191"
    expect:
      contains: "ep-0191"
```

## Logs

| Path | Contents |
|------|----------|
| `dev/logs/sessions/` | Exported session JSONL (like `/newchat`) |
| `dev/logs/runs/` | Scenario run JSON reports |
| `dev/logs/sandbox/` | Janitor temp vaults (gitignored) |

## CI

[`tests/test_harness_scenarios.py`](../tests/test_harness_scenarios.py) parametrizes every `dev/scenarios/**/*.yaml` in **echo** mode. They run as part of default CI:

```bash
pytest tests -q
```

Opt out locally or in CI:

```bash
SKIP_HARNESS_SCENARIOS=1 pytest tests -q
```

## Not the same as retrieval scenarios

| | Mock Telegram harness | Vault retrieval scenarios |
|--|------------------------|---------------------------|
| **Files** | `dev/scenarios/*.yaml` | `ingestion/fixtures/vault_retrieval_scenarios.jsonl` |
| **Tests** | `test_harness_scenarios.py` | `test_vault_retrieval_scenarios.py` |
| **Checks** | Bot commands, replies, Janitor FSM | Chunk index / hybrid search quality |
| **Rebuilt index** | Uses live `catalog/chunks.jsonl` in echo | Optional `RUN_REBUILT_INDEX_SCENARIOS=1` |

## Layout

```text
dev/
  mock_telegram_cli.py      # CLI entry
  harness/
    mock_session.py         # MockBotSession + echo LLM patches
    scenario_runner.py      # YAML loader + assertions
    janitor_sandbox.py      # Temp vault for Janitor
    terminal.py             # REPL
  scenarios/
    librarian/*.yaml
    janitor/*.yaml
```

## History

Shipped in [PR #10](https://github.com/ethan-frost-xyz/founders-notes/pull/10). Design notes: [`.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md`](../.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md).
