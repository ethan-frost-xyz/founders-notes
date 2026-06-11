# Telegram mock harness

Headless and interactive testing for the **Librarian** and **Janitor** Telegram bot **without the real Bot API**. The harness runs the production handler stack (`build_application()`) with a mocked outbound transport; handler routing, sessions, Janitor FSM, and tool loops behave like production.

**When to use:** Before shipping handler or Janitor changes; adding YAML regressions; tuning agent prompts on the **Mac mini** (or laptop). Uses a mocked Bot API — safe to run while the launchd bot is polling.

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

**`-v` / `--verbose`:** prints `tools_called` per turn, agent path string, latency breakdown (routing / expand / hybrid / rerank / final TTFT / thrash score), and a one-line **timing** summary per turn — use when a live turn fails or you are profiling slowness.

### Timing

Per-turn phase timing is **on by default in the harness** (disable with `LIBRARIAN_TIMING=0`). Production Telegram bot timing is **off** unless `LIBRARIAN_TIMING=1` in `~/.config/founders-telegram/env` (appends JSONL on macOS).

```bash
# Per-turn phase line + suite aggregate table
python dev/mock_telegram_cli.py --suite librarian --live-only -v
```

**Verbose output example:**

```text
PASS thematic_search (64.0s, live) | path: search_vault
  [ok] turn 1: send '...' — ok [vault=120ms retrieval_llm=800ms ttft=450ms tok/s=38.2]
    latency: routing=2.1s expand=0.8s hybrid=0.1s rerank=0.7s final_ttft=4.5s
```

**Report JSON** (`dev/logs/runs/*-report.json`): schema **v2.0** with `observability` per turn when timing is enabled (harness default on).

**Suite aggregate** (printed after all scenarios with `-v`): legacy timing means plus `cap_hits`, `mean_final_ttft_ms`, `mean_thrash_score`.

**Librarian suite history:** `dev/logs/runs/librarian-suite-history.json` — append-only registry of librarian runs with `delta_vs_baseline` when a baseline is set.

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
| `-v` / `--verbose` | Tool names, agent path, latency breakdown, timing summary; suite aggregate; preflight on live runs |
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
| `dev/logs/runs/` | `*-report.json` (v2 observability), `*-report.md` (live librarian), `librarian-suite-history.json` |
| `dev/logs/sandbox/` | Janitor temp vaults (gitignored) |

On failure, read the latest `dev/logs/runs/*-report.json`. For live librarian quality review, open the paired `*-report.md` in a markdown preview. Use `-v` on the CLI for per-turn timing lines and suite aggregates on stdout.

**Remote (Mac mini):** runs write to `dev/logs/runs/` on the mini; reports are **git-tracked** — `./dev/pull-harness-reports.sh` rsyncs to the laptop before commit, or push from the mini. See [operations.md](operations.md) (Tailscale section).

### Report JSON schema (`*-report.json`)

Written on every scenario run (not gated on `-v`). **`schema_version`: `"2.0"`** — legacy top-level turn fields retained for one release.

**Suite level:** `schema_version`, `harness_version` (git sha), `suite` (`librarian` / `janitor` / null), `passed`, `generated_at`, `scenario_count`, `aggregate` (when timing on), `scenarios[]`.

**Aggregate (`aggregate`):** `pass_count`, `scenario_count`, `cap_hits`, `mean_wall_s`, `mean_final_ttft_ms`, `mean_thrash_score`, plus legacy timing rollups when present.

**Per turn (always):**

| Field | Purpose |
|-------|---------|
| `response_text` | Agent final markdown (`result.content`) — clean answer for quality review |
| `stop_reason` | `natural`, `cap` (hit 6 tool rounds), or `error` |
| `tool_calls` | Flat list with `tool`, `arguments`, `step` |
| `tool_rounds` | Per agent round: `tools`, `queries`, `episode_ids`, `rerank_scores_top3`, `evidence` |
| `tool_call_counts` | Counts by tool name (e.g. transcript stacking) |
| `trace_summary` | Human-readable multiline trace |
| `tools_called` | Legacy flat tool names (unchanged) |
| `timing` | When Librarian timing is recorded (harness default on) |
| `timing_summary` | One-line timing bucket summary |
| `timing_accountability` | `wall_ms` vs wall-based buckets; see breakdown below |
| `observability` | Derived metrics block (when `LIBRARIAN_TIMING != 0`) |

**Observability (`observability`) — per turn:**

| Sub-block | Purpose |
|-----------|---------|
| `agent_path` | `sequence`, `path_string` (e.g. `search_vault -> search_transcript`), `tool_rounds_used`, `reasoning_snippets` |
| `routing_efficiency` | `redundant_queries`, `search_before_load_pattern`, `tool_switches` |
| `latency` | `wall_ms`, `agent_routing_ms`, `retrieval.*_ms` spans, `tool_local_ms`, `synthesis.final_ttft_ms`, `accountability` |
| `evidence_yield` | `chunks_per_round`, `unique_episodes_per_round`, `rerank_top_score_per_round` |
| `synthesis_quality` | `citation_count`, `dsml_leak`, `final_synthesis_ttft_ms` |
| `cap_thrash` | When cap hit: gathered round shares + cited `[ep-NNNN]` utilization |

**Span source (`tool_trace` record `spans`):** `retrieval.query_expand`, `retrieval.hybrid_search`, `retrieval.llm_rerank`, `retrieval.transcript_fallback`, `retrieval.rerank_fallback`, `agent.routing`, `agent.synthesis.final`. New retrieval stages can add `retrieval.*` names without a schema bump.

**Timing notes (legacy `timing` block):**

- `timing.searches[]` rows include `tool` (`search_vault`, `search_vault_many`, `search_transcript`), optional `wall_ms`, and optional `error`.
- `openrouter_calls` covers agent LLM streams only — not vault/transcript tool execution wall time.
- `agent_ttft_ms_mean` averages **all** agent rounds (tool-pick and synthesis). Use `observability.latency.synthesis.final_ttft_ms` for **final answer** TTFT.
- **`timing_accountability` math:** `accounted_ms = search_wall_ms + tool_local_ms + openrouter_total_ms`. For consecutive `search_vault_many` rows, `search_wall_ms` uses **max** `wall_ms` per batch (not sum). Flag `unaccounted_ms` >60s on turns with heavy local tools or agent overhead.

### Librarian suite history (`librarian-suite-history.json`)

Appended automatically when running scenarios under `dev/scenarios/librarian/`.

| Field | Purpose |
|-------|---------|
| `schema_version` | `"1.0"` |
| `baseline_run_id` | First run id unless overridden |
| `runs[]` | `run_id`, `report_path`, `markdown_path`, `harness_version`, `pass_count`, `total_wall_s`, `cap_hits`, `delta_vs_baseline`, `observability_aggregate` |

Set `baseline_run_id` manually in the history file to pin a comparison target for `delta_vs_baseline` (`pass_count_delta`, `wall_pct`, `cap_hits_delta`).

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
    scenario_runner.py      # YAML loader + assertions + v2 reports
    observability.py        # Derived metrics from tool traces
    suite_history.py        # Librarian suite history append
    report_meta.py          # schema_version + git sha
    trace_report.py         # Trace → report field extractors
    janitor_sandbox.py      # Temp vault for Janitor
    terminal.py             # REPL
  scenarios/
    README.md
    librarian/*.yaml
    janitor/*.yaml
```

## History

Shipped in [PR #10](https://github.com/ethan-frost-xyz/founders-notes/pull/10). Historical design notes: `.cursor/plans/archive/legacy/telegram_mock_harness_2296d9fc.plan.md`.
