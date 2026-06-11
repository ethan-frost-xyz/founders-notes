# Telegram mock harness

Headless and interactive testing for the **Librarian** and **Janitor** Telegram bot **without the real Bot API**. The harness runs the production handler stack (`build_application()`) with a mocked outbound transport; handler routing, sessions, Janitor FSM, and tool loops behave like production.

**When to use:** Before shipping handler or Janitor changes; adding YAML regressions; tuning agent prompts on the **Mac mini** (or laptop). Uses a mocked Bot API — safe to run while the launchd bot is polling.

**Related:** [testing.md](testing.md) (CI and test-module index) · [services/telegram/README.md](../services/telegram/README.md) (Mac mini runbook) · [janitor.md](janitor.md) (operator workflow)

## Testing layers

| Layer | What it proves | Command | CI |
|-------|----------------|---------|-----|
| **Tool unit** | `load_episode` (incl. ambiguous → `candidates`), `list_episode_ids`, `resolve_episode_ref` | `pytest tests/test_vault_agent.py -q` | Yes |
| **Handler unit** | Librarian/Janitor/Settings callback wiring (mocked agent/workflow) | `pytest tests/test_telegram_handlers.py tests/test_janitor_handlers.py tests/test_settings_handlers.py -q` | Yes |
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
| **Live** | Omit `--stub-llm` and use `llm: live` in YAML | `OPENROUTER_API_KEY`; `librarian_model` / `retrieval_model` in `runtime.json` or legacy `TELEGRAM_CHAT_MODEL` / `TELEGRAM_RETRIEVAL_MODEL` in env | Echo assertions plus `expect_live`: `tool_called`, `response_contains`, `load_episode_id`, etc. |

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

**`-v` / `--verbose`:** prints `tools_called` per turn, a one-line **timing** summary per turn (pickup / vault local / retrieval LLM / agent TTFT / tok/s), and adds them to `dev/logs/runs/*-report.json` — use when a live turn fails or you are profiling slowness.

### Timing

Per-turn phase timing is **on by default in the harness** (disable with `LIBRARIAN_TIMING=0`). Production Telegram bot timing is **off** unless `LIBRARIAN_TIMING=1` in `~/.config/founders-telegram/env` (appends JSONL on macOS).

```bash
# Per-turn phase line + suite aggregate table
python dev/mock_telegram_cli.py --suite librarian --live-only -v
```

**Verbose output example:** `[vault=120ms retrieval_llm=800ms ttft=450ms tok/s=38.2]`

**Report JSON** (`dev/logs/runs/*-report.json`, when `-v`): each turn may include `timing` (dict) and `timing_summary` (string).

**Suite aggregate** (printed after all scenarios with `-v`): mean/sum for `vault_search_local_ms`, `retrieval_llm_ms`, agent TTFT, and tok/s across turns.

**Production JSONL:** `~/Library/Logs/founders-telegram/librarian-timing.jsonl` (macOS only; one line per turn when enabled).

| Bucket | Meaning |
|--------|---------|
| `telegram_pickup_ms` | Telegram message date → handler start (production only; null in harness) |
| `vault_search_local_ms` | Embed + hybrid search + transcript keyword (**effort** total; can exceed wall when `search_vault_many` fans out) |
| `retrieval_llm_ms` | Expand + rerank OpenRouter wall time (**effort** total; same concurrent caveat) |
| `thread_wait_ms` | Parent wall waiting on `search_vault_many` `ThreadPoolExecutor` (diagnostic) |
| `expand_retry_ms` | OpenRouter expand/rerank retry backoff + failed-attempt wall (diagnostic) |
| `tool_local_ms` | `load_episode` / `list_episode_ids` disk + catalog work |
| `agent_ttft_ms_mean` | Mean time-to-first-token across agent-loop completions |
| `generation_tok_per_sec_mean` | Mean inter-token speed for streamed agent completions |

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
| `-v` / `--verbose` | Tool names + timing summary per turn; preflight summary on live runs; suite timing aggregate |
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

**Expect keys:** `contains`, `not_contains`, `response_min_length`, `expect_live` (`tool_called`, `tool_called_any`, `tools_called`, `response_contains`, `response_contains_any`, `load_episode_id`, `status_contains`), `phase` (Janitor), `sandbox_file_written` (substring match on sandbox paths). Harness bot keeps status messages (not deleted) so `status_contains: "Searching vault"` is testable.

`tool_called_any` passes when **any** listed tool name appears in the turn trace (live only). Use for cross-episode thematic turns where `search_vault` or `search_vault_many` are both valid per [`AGENTS.md`](../AGENTS.md).

**Agentic Librarian tools (live assertions):** `search_vault`, `search_vault_many`, `search_transcript`, `load_episode`, `list_episode_ids`. Hard-question scenarios live under `dev/scenarios/librarian/` (`multi_founder_comparison`, `thin_evidence_probe`, `verbatim_transcript`, `multi_hop`, `single_founder_depth`).

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
| `dev/logs/runs/` | `*-report.json` (full trace) and paired `*-report.md` for live librarian runs |
| `dev/logs/sandbox/` | Janitor temp vaults (gitignored) |

On failure, read the latest `dev/logs/runs/*-report.json`. For live librarian quality review, open the paired `*-report.md` in a markdown preview. Use `-v` on the CLI for per-turn timing lines and suite aggregates on stdout.

### Report JSON schema (`*-report.json`)

Written on every scenario run (not gated on `-v`).

**Suite level:** `passed`, `generated_at`, `scenario_count`, `scenarios[]`.

**Per turn (always):**

| Field | Purpose |
|-------|---------|
| `response_text` | Agent final markdown (`result.content`) — clean answer for quality review |
| `stop_reason` | `natural`, `cap` (hit 6 tool rounds), or `error` |
| `tool_calls` | Flat list with `tool`, `arguments`, `step` |
| `tool_rounds` | Per agent round: `tools`, `queries`, `episode_ids`, `rerank_scores_top3` |
| `tool_call_counts` | Counts by tool name (e.g. transcript stacking) |
| `trace_summary` | Human-readable multiline trace |
| `tools_called` | Legacy flat tool names (unchanged) |
| `timing` | When Librarian timing is recorded (harness default on) |
| `timing_summary` | One-line timing bucket summary |
| `timing_accountability` | `wall_ms` vs wall-based buckets; see breakdown below |

**Timing notes:**

- `timing.searches[]` rows include `tool` (`search_vault`, `search_vault_many`, `search_transcript`), optional `wall_ms`, and optional `error`.
- `openrouter_calls` covers agent LLM streams only — not vault/transcript tool execution wall time.
- `agent_ttft_ms_mean` averages all agent rounds (tool-pick and synthesis).
- **`timing_accountability` math:** `accounted_ms = search_wall_ms + tool_local_ms + openrouter_total_ms`. For consecutive `search_vault_many` rows, `search_wall_ms` uses **max** `wall_ms` per batch (not sum). `vault_search_local_ms` / `retrieval_llm_ms` remain effort totals; `parallelism_excess_ms` in the breakdown shows their over-count vs wall. Flag `unaccounted_ms` >60s on turns with heavy local tools or agent overhead.

### Report markdown (`*-report.md`)

Written alongside JSON when the run includes **live** scenarios under `dev/scenarios/librarian/`. Not written for echo/stub CI or Janitor-only runs.

Contains agent answers only (no tool traces or timing): scenario headings with PASS/FAIL, turn headings, blockquoted user prompts, then the raw librarian markdown body. Same timestamp as the JSON report (`2026-06-09T18-25-19-report.md` next to `-report.json`).

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

Shipped in [PR #10](https://github.com/ethan-frost-xyz/founders-notes/pull/10). Historical design notes: `.cursor/plans/archive/legacy/telegram_mock_harness_2296d9fc.plan.md`.
