# Telegram mock harness

Headless and interactive testing for the **Librarian** and **Janitor** Telegram bot **without the real Bot API**. The harness runs the production handler stack (`build_application()`) with a mocked outbound transport; handler routing, sessions, Janitor FSM, and tool loops behave like production.

**When to use:** Before shipping handler or Janitor changes; adding YAML regressions; tuning agent prompts locally.

**Related:** [testing.md](testing.md) (CI and test-module index) · [services/telegram/README.md](../services/telegram/README.md) (Mac mini runbook) · [janitor.md](janitor.md) (operator workflow)

## Testing layers

| Layer | What it proves | Command | CI |
|-------|----------------|---------|-----|
| **Tool unit** | `load_episode` (incl. ambiguous → `candidates`), `list_episode_ids`, `resolve_episode_ref` | `pytest tests/test_vault_agent.py -q` | Yes |
| **Harness echo** | Handlers, commands, Janitor FSM (stub LLM) | `pytest tests/test_harness_scenarios.py -q` | Yes (~seconds; not the pytest bottleneck) |
| **Harness live** | Full Librarian tool loop + OpenRouter | `python dev/mock_telegram_cli.py --suite librarian --live-only -v` | No (opt-in pytest below) |
| **Real Telegram** | Production bot + Bot API | Mac mini manual smoke | No |

Vault **retrieval** JSONL scenarios (`test_vault_retrieval_scenarios.py`) measure chunk index quality only — not bot UX.

## Quick start

From repo root (after `pip install -r ingestion/requirements.txt -r ingestion/requirements-dev.txt`):

```bash
# All scenarios, echo LLM (no API keys) — same as CI
pytest tests/test_harness_scenarios.py -q
# or:
python dev/mock_telegram_cli.py --stub-llm --run-scenarios

# One suite or file (--suite / --scenario imply run mode; no --run-scenarios needed)
python dev/mock_telegram_cli.py --stub-llm --suite janitor
python dev/mock_telegram_cli.py --stub-llm --scenario dev/scenarios/janitor/episode_parse.yaml

# Interactive REPL with tool traces (echo — use --stub-llm)
python dev/mock_telegram_cli.py --stub-llm --debug
```

`TELEGRAM_BOT_TOKEN` is never required.

## Echo vs live

| Mode | How | API key | Assertions checked |
|------|-----|---------|-------------------|
| **Echo** | `--stub-llm` on CLI, or `llm: echo` in scenario YAML | Not required | `contains`, `not_contains`, `response_min_length`; Janitor `phase`, `sandbox_file_written` |
| **Live** | Omit `--stub-llm` and use `llm: live` in YAML | `OPENROUTER_API_KEY`; `TELEGRAM_CHAT_MODEL` in env **or** `librarian_model` in `runtime.json` (harness reads both) | Echo assertions plus `expect_live`: `tool_called`, `response_contains`, `load_episode_id`, etc. |

In **echo** mode, `expect_live` blocks in YAML are skipped (CI uses echo only). Librarian scenarios marked `llm: live` still run in echo when you pass `--stub-llm` or when `tests/test_harness_scenarios.py` sets `stub_llm=True` — they only check non-live keys unless you run without `--stub-llm`.

### Live smoke

The CLI loads env automatically (existing shell vars win):

1. `FOUNDERS_TELEGRAM_ENV` or `~/.config/founders-telegram/env`
2. Repo `{VAULT_ROOT}/.env`

**Preflight** checks API keys, `catalog/chunks.jsonl`, and `catalog/embeddings.npy` on the clone before live Librarian runs:

```bash
python dev/mock_telegram_cli.py --preflight
```

```bash
# Librarian suite only (5 scenarios, ~8 min)
python dev/mock_telegram_cli.py --suite librarian --live-only -v

# Episode resolution regression (NL “episode 191”)
python dev/mock_telegram_cli.py --scenario dev/scenarios/librarian/episode_resolve.yaml -v
```

**`-v` / `--verbose`:** prints `tools_called` per turn and adds them to `dev/logs/runs/*-report.json` — use when a live turn fails.

**Opt-in pytest** (same OpenRouter requirements):

```bash
RUN_LIVE_HARNESS=1 pytest tests/test_harness_scenarios.py -k live -q
```

## CLI reference

| Flag | Effect |
|------|--------|
| `--scenario PATH` | Run one YAML file (implies scenario mode) |
| `--suite NAME` | Run `dev/scenarios/NAME/**/*.yaml` (implies scenario mode) |
| `--run-scenarios` | Run all scenarios (optional if `--suite` or `--scenario` set) |
| `--live-only` | Skip scenarios with `llm: echo` |
| `--stub-llm` | Echo LLM; no OpenRouter |
| `--preflight` | Print live env + index checks and exit |
| `-v` / `--verbose` | Tool names per turn + richer failure messages; preflight summary on live runs |
| `--debug` | REPL: show tool traces |
| `--keep-sandbox` | Keep Janitor temp dirs under `dev/logs/sandbox/` |

**REPL:** `python dev/mock_telegram_cli.py` with no scenario flags starts interactive mode. Default LLM is **live** (needs keys). Use **`--stub-llm`** for keyless debugging.

**Common mistake (fixed):** `python dev/mock_telegram_cli.py --suite librarian` used to open the REPL; it now runs scenarios. Use a bare CLI invocation only when you want the REPL.

## REPL default

Running `python dev/mock_telegram_cli.py` **without** `--scenario`, `--suite`, or `--run-scenarios` starts an interactive REPL. The default LLM mode is **live** (needs OpenRouter env). For keyless local debugging, always pass **`--stub-llm`**.

## Janitor sandbox

Janitor scenarios set `janitor_episode` (e.g. `ep-0191`). Writes go to a temp tree under `dev/logs/sandbox/`, never to `content/notes/` in the real vault.

- In-process paths are patched via [`dev/harness/janitor_sandbox.py`](../dev/harness/janitor_sandbox.py).
- Echo mode stubs expand/reindex subprocesses; full workflow is still exercised for handlers and buttons.

Use `--keep-sandbox` on the CLI to preserve sandbox dirs after a run.

## Scenario YAML

Files live under [`dev/scenarios/`](../dev/scenarios/) (`librarian/`, `janitor/`). See [`dev/scenarios/README.md`](../dev/scenarios/README.md) for a file index.

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

**Expect keys:** `contains`, `not_contains`, `response_min_length`, `expect_live` (`tool_called`, `tools_called`, `response_contains`, `response_contains_any`, `load_episode_id`, `status_contains`), `phase` (Janitor), `sandbox_file_written` (substring match on sandbox paths). Harness bot keeps status messages (not deleted) so `status_contains: "Searching notes"` is testable.

`load_episode_id` checks that a `load_episode` tool call used an `episode_id` that resolves to the canonical id (stable when the model omits `[ep-NNNN]` from prose).

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

Example (Librarian NL episode resolve — live only):

```yaml
name: Librarian episode resolve NL
llm: live
turns:
  - send: "What did I note on episode 191?"
    expect:
      response_min_length: 40
      not_contains: "Episode not in catalog"
      expect_live:
        tool_called: load_episode
        load_episode_id: ep-0191
```

## Logs

| Path | Contents |
|------|----------|
| `dev/logs/sessions/` | Exported session JSONL (like `/newchat`) |
| `dev/logs/runs/` | Scenario run JSON reports (`tools_called` per turn when verbose) |
| `dev/logs/sandbox/` | Janitor temp vaults (gitignored) |

On failure, read the latest `dev/logs/runs/*-report.json` and re-run with `-v`.

## CI

[`tests/test_harness_scenarios.py`](../tests/test_harness_scenarios.py) parametrizes every `dev/scenarios/**/*.yaml` in **echo** mode. They run as part of default CI:

```bash
pytest tests -q
```

Opt out locally or in CI:

```bash
SKIP_HARNESS_SCENARIOS=1 pytest tests -q
```

Live OpenRouter scenarios: `RUN_LIVE_HARNESS=1 pytest tests/test_harness_scenarios.py -k live -q` (not in default CI).

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
    env.py                  # Auto-load founders-telegram + repo .env
    mock_session.py         # MockBotSession + echo LLM patches
    scenario_runner.py      # YAML loader + assertions
    janitor_sandbox.py      # Temp vault for Janitor
    terminal.py             # REPL
  scenarios/
    README.md
    librarian/*.yaml
    janitor/*.yaml
```

## History

Shipped in [PR #10](https://github.com/ethan-frost-xyz/founders-notes/pull/10). Design notes: [`.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md`](../.cursor/plans/archive/telegram_mock_harness_2296d9fc.plan.md).
